from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import Payment,PaymentWebhookEvent

def create_payment(*,order,method,amount): return Payment.objects.create(order=order,method=method,amount=amount)
@transaction.atomic
def mark_payment_paid(*,payment,transaction_id="",gateway_reference=""):
    payment=Payment.objects.select_for_update().get(pk=payment.pk)
    from apps.orders.models import Order
    order=Order.objects.select_for_update().get(pk=payment.order_id)
    if payment.status==Payment.Status.PAID:return payment
    if payment.status not in {Payment.Status.PENDING,Payment.Status.AUTHORIZED}: raise ValidationError({"payment":"Payment cannot transition to paid."})
    payment.status=Payment.Status.PAID; payment.transaction_id=transaction_id or payment.transaction_id; payment.gateway_reference=gateway_reference or payment.gateway_reference; payment.paid_at=timezone.now(); payment.save(update_fields=["status","transaction_id","gateway_reference","paid_at","updated_at"])
    order.payment_status=Order.PaymentStatus.PAID; order.save(update_fields=["payment_status","updated_at"]); return payment

def process_webhook(*,provider,event_id,payload,handler):
    event,created=PaymentWebhookEvent.objects.get_or_create(provider=provider,event_id=event_id,defaults={"payload":payload})
    if not created:return event,False
    try:
        with transaction.atomic(): handler(payload)
    except Exception as exc:
        event.processing_error=str(exc); event.save(update_fields=["processing_error","updated_at"]); raise
    event.processed_at=timezone.now(); event.save(update_fields=["processed_at","updated_at"]); return event,True
