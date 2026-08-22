from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.orders.models import Order,OrderItem
from apps.orders.services import transition_order
from apps.inventory.services import resolve_stock_item,increase_stock
from apps.inventory.models import StockMovement
from apps.payments.models import Payment
from .models import ReturnRequest,ReturnItem,Refund
@transaction.atomic
def create_return_request(*,order,user,items,reason):
    order=Order.objects.select_for_update().get(pk=order.pk,user=user)
    if order.order_status not in {Order.Status.DELIVERED,Order.Status.RETURN_REQUESTED,Order.Status.PARTIALLY_RETURNED}: raise ValidationError({"order":"Only delivered orders can be returned."})
    rr=ReturnRequest.objects.create(order=order,user=user,reason=reason)
    for row in items:
        oi=OrderItem.objects.select_for_update().get(pk=row["order_item"].pk,order=order); qty=int(row["quantity"])
        pending=ReturnItem.objects.filter(order_item=oi).exclude(return_request__status=ReturnRequest.Status.REJECTED).aggregate(x=Sum("quantity"))["x"] or 0
        if qty<=0 or pending+qty>oi.quantity: raise ValidationError({"quantity":f"Return quantity exceeds purchased quantity for item {oi.id}."})
        ReturnItem.objects.create(return_request=rr,order_item=oi,quantity=qty,reason=row.get("reason",""),restock=row.get("restock",True))
    if order.order_status==Order.Status.DELIVERED: transition_order(order=order,new_status=Order.Status.RETURN_REQUESTED)
    return rr
@transaction.atomic
def receive_return(*,return_request,warehouse,actor=None):
    rr=ReturnRequest.objects.select_for_update().prefetch_related("items__order_item__product","items__order_item__variant__product").get(pk=return_request.pk)
    if rr.status != ReturnRequest.Status.APPROVED: raise ValidationError({"return":"Return must be approved before receiving."})
    for ri in rr.items.all():
        oi=OrderItem.objects.select_for_update().get(pk=ri.order_item_id)
        if oi.returned_quantity+ri.quantity>oi.quantity: raise ValidationError({"quantity":"Return quantity exceeds purchased quantity."})
        oi.returned_quantity+=ri.quantity; oi.save(update_fields=["returned_quantity","updated_at"])
        if ri.restock:
            si=resolve_stock_item(product=oi.product if not oi.variant_id else None,variant=oi.variant)
            increase_stock(stock_item=si,warehouse=warehouse,quantity=ri.quantity,movement_type=StockMovement.Type.RETURN,reference_type="return_item",reference_id=ri.id,note=f"Return for {rr.order.order_number}",created_by=actor)
    rr.status=ReturnRequest.Status.RECEIVED; rr.reviewed_by=actor; rr.save(update_fields=["status","reviewed_by","updated_at"])
    order=Order.objects.select_for_update().prefetch_related("items").get(pk=rr.order_id); total=sum(i.quantity for i in order.items.all()); returned=sum(i.returned_quantity for i in order.items.all()); target=Order.Status.RETURNED if returned>=total else Order.Status.PARTIALLY_RETURNED; transition_order(order=order,new_status=target,actor=actor); return rr
@transaction.atomic
def create_refund(*,payment,amount,reason="",actor=None):
    payment=Payment.objects.select_for_update().select_related("order").get(pk=payment.pk)
    if payment.status not in {Payment.Status.PAID,Payment.Status.PARTIAL_REFUND}: raise ValidationError({"payment":"Only paid payments can be refunded."})
    allocated=Refund.objects.filter(payment=payment,status__in=[Refund.Status.PENDING,Refund.Status.PROCESSING,Refund.Status.COMPLETED]).aggregate(x=Sum("amount"))["x"] or 0
    if amount<=0 or allocated+amount>payment.amount: raise ValidationError({"amount":"Total refunded amount cannot exceed amount paid."})
    return Refund.objects.create(order=payment.order,payment=payment,amount=amount,reason=reason,created_by=actor)
@transaction.atomic
def complete_refund(*,refund,gateway_reference=""):
    refund=Refund.objects.select_for_update().get(pk=refund.pk)
    payment=Payment.objects.select_for_update().get(pk=refund.payment_id)
    order=Order.objects.select_for_update().get(pk=refund.order_id)
    if refund.status==Refund.Status.COMPLETED:return refund
    if refund.status not in {Refund.Status.PENDING,Refund.Status.PROCESSING}: raise ValidationError({"refund":"Refund cannot be completed."})
    refund.status=Refund.Status.COMPLETED; refund.gateway_reference=gateway_reference; refund.completed_at=timezone.now(); refund.save(update_fields=["status","gateway_reference","completed_at","updated_at"])
    total=Refund.objects.filter(payment=payment,status=Refund.Status.COMPLETED).aggregate(x=Sum("amount"))["x"] or 0
    full=total>=payment.amount; payment.status=Payment.Status.REFUNDED if full else Payment.Status.PARTIAL_REFUND; payment.save(update_fields=["status","updated_at"]); order.payment_status=Order.PaymentStatus.REFUNDED if full else Order.PaymentStatus.PARTIAL_REFUND; order.save(update_fields=["payment_status","updated_at"]);
    if full and order.order_status!=Order.Status.REFUNDED: transition_order(order=order,new_status=Order.Status.REFUNDED)
    return refund

@transaction.atomic
def approve_return(*,return_request,actor=None):
    rr=ReturnRequest.objects.select_for_update().get(pk=return_request.pk)
    if rr.status!=ReturnRequest.Status.REQUESTED: raise ValidationError({"return":"Only requested returns can be approved."})
    rr.status=ReturnRequest.Status.APPROVED; rr.reviewed_by=actor; rr.save(update_fields=["status","reviewed_by","updated_at"]); return rr
@transaction.atomic
def reject_return(*,return_request,actor=None,notes=""):
    rr=ReturnRequest.objects.select_for_update().get(pk=return_request.pk)
    if rr.status!=ReturnRequest.Status.REQUESTED: raise ValidationError({"return":"Only requested returns can be rejected."})
    rr.status=ReturnRequest.Status.REJECTED; rr.reviewed_by=actor; rr.notes=notes or rr.notes; rr.save(update_fields=["status","reviewed_by","notes","updated_at"])
    order=Order.objects.select_for_update().get(pk=rr.order_id)
    if not order.return_requests.exclude(pk=rr.pk).filter(status__in=[ReturnRequest.Status.REQUESTED,ReturnRequest.Status.APPROVED]).exists() and order.order_status==Order.Status.RETURN_REQUESTED:
        transition_order(order=order,new_status=Order.Status.DELIVERED,actor=actor)
    return rr
