from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import StockItem,ProductStock,StockMovement,StockReservation,Purchase,PurchaseItem
from apps.catalog.models import Product

def resolve_stock_item(*,product=None,variant=None,create=True):
    if bool(product)==bool(variant): raise ValidationError({"inventory_target":"Exactly one of product or variant is required."})
    if product:
        if product.product_type!=Product.ProductType.SIMPLE: raise ValidationError({"product":"Variable products require a variant."})
        obj,created=StockItem.objects.get_or_create(product=product,defaults={"variant":None}) if create else (StockItem.objects.get(product=product),False)
    else:
        if variant.product.product_type!=Product.ProductType.VARIABLE: raise ValidationError({"variant":"Variant target is invalid."})
        obj,created=StockItem.objects.get_or_create(variant=variant,defaults={"product":None}) if create else (StockItem.objects.get(variant=variant),False)
    return obj

def get_sellable_stock(*,stock_item):
    return stock_item.stocks.aggregate(total=Sum("available_stock"))["total"] or 0

def _movement(stock,kind,qty,before,after,reference_type="",reference_id="",note="",created_by=None):
    return StockMovement.objects.create(stock_item=stock.stock_item,warehouse=stock.warehouse,movement_type=kind,quantity=qty,before_quantity=before,after_quantity=after,reference_type=reference_type,reference_id=str(reference_id or ""),note=note,created_by=created_by)

@transaction.atomic
def increase_stock(*,stock_item,warehouse,quantity,movement_type=StockMovement.Type.RESTOCK,reference_type="",reference_id="",note="",created_by=None):
    if quantity<=0: raise ValidationError({"quantity":"Must be greater than zero."})
    stock,_=ProductStock.objects.select_for_update().get_or_create(stock_item=stock_item,warehouse=warehouse)
    before=stock.available_stock; stock.available_stock += quantity; stock.save(update_fields=["available_stock","updated_at"])
    _movement(stock,movement_type,quantity,before,stock.available_stock,reference_type,reference_id,note,created_by); return stock

@transaction.atomic
def decrease_stock(*,stock_item,warehouse,quantity,movement_type=StockMovement.Type.ADJUSTMENT,reference_type="",reference_id="",note="",created_by=None):
    if quantity<=0: raise ValidationError({"quantity":"Must be greater than zero."})
    stock=ProductStock.objects.select_for_update().get(stock_item=stock_item,warehouse=warehouse)
    if stock.available_stock<quantity: raise ValidationError({"stock":"Insufficient available stock."})
    before=stock.available_stock; stock.available_stock-=quantity; stock.save(update_fields=["available_stock","updated_at"])
    _movement(stock,movement_type,-quantity,before,stock.available_stock,reference_type,reference_id,note,created_by); return stock

@transaction.atomic
def reserve_stock(*,stock_item,quantity,reference_type,reference_id,warehouse=None,created_by=None):
    if quantity<=0: raise ValidationError({"quantity":"Must be greater than zero."})
    qs=ProductStock.objects.select_for_update().filter(stock_item=stock_item,warehouse__is_active=True)
    if warehouse: qs=qs.filter(warehouse=warehouse)
    stocks=list(qs.order_by("warehouse_id"))
    if sum(s.available_stock for s in stocks)<quantity: raise ValidationError({"stock":"Insufficient sellable stock."})
    remaining=quantity; reservations=[]
    for stock in stocks:
        take=min(stock.available_stock,remaining)
        if not take: continue
        before=stock.available_stock; stock.available_stock-=take; stock.reserved_stock+=take; stock.save(update_fields=["available_stock","reserved_stock","updated_at"])
        reservation=StockReservation.objects.create(stock_item=stock_item,warehouse=stock.warehouse,quantity=take,reference_type=reference_type,reference_id=str(reference_id))
        reservations.append(reservation); _movement(stock,StockMovement.Type.RESERVATION,-take,before,stock.available_stock,reference_type,reference_id,"Stock reserved",created_by)
        remaining-=take
        if remaining==0: break
    return reservations

@transaction.atomic
def release_stock(*,reference_type,reference_id,created_by=None):
    reservations=list(StockReservation.objects.select_for_update().filter(reference_type=reference_type,reference_id=str(reference_id),consumed=False,released=False).select_related("stock_item","warehouse"))
    for r in reservations:
        stock=ProductStock.objects.select_for_update().get(stock_item=r.stock_item,warehouse=r.warehouse)
        if stock.reserved_stock<r.quantity: raise ValidationError({"stock":"Reservation ledger is inconsistent."})
        before=stock.available_stock; stock.reserved_stock-=r.quantity; stock.available_stock+=r.quantity; stock.save(update_fields=["available_stock","reserved_stock","updated_at"])
        r.released=True; r.save(update_fields=["released","updated_at"]); _movement(stock,StockMovement.Type.CANCELLATION,r.quantity,before,stock.available_stock,reference_type,reference_id,"Reservation released",created_by)
    return reservations

@transaction.atomic
def consume_reserved_stock(*,reference_type,reference_id,created_by=None):
    reservations=list(StockReservation.objects.select_for_update().filter(reference_type=reference_type,reference_id=str(reference_id),consumed=False,released=False).select_related("stock_item","warehouse"))
    if not reservations: raise ValidationError({"stock":"No active reservation found."})
    for r in reservations:
        stock=ProductStock.objects.select_for_update().get(stock_item=r.stock_item,warehouse=r.warehouse)
        if stock.reserved_stock<r.quantity: raise ValidationError({"stock":"Reservation ledger is inconsistent."})
        before=stock.available_stock; stock.reserved_stock-=r.quantity; stock.save(update_fields=["reserved_stock","updated_at"])
        r.consumed=True; r.save(update_fields=["consumed","updated_at"]); _movement(stock,StockMovement.Type.SALE,-r.quantity,before,stock.available_stock,reference_type,reference_id,"Reserved stock consumed",created_by)
    return reservations

@transaction.atomic
def adjust_stock(*,stock_item,warehouse,new_quantity=None,mode="set",quantity=None,note="Stock adjustment",created_by=None):
    stock,_=ProductStock.objects.select_for_update().get_or_create(stock_item=stock_item,warehouse=warehouse)
    before=stock.available_stock
    if mode=="increase": target=before+int(quantity or 0)
    elif mode=="decrease": target=before-int(quantity or 0)
    else: target=int(new_quantity if new_quantity is not None else before)
    if target<0: raise ValidationError({"quantity":"Adjustment cannot make available stock negative."})
    delta=target-before; stock.available_stock=target; stock.save(update_fields=["available_stock","updated_at"])
    _movement(stock,StockMovement.Type.ADJUSTMENT,delta,before,target,"adjustment",stock.pk,note,created_by); return stock

@transaction.atomic
def transfer_stock(*,stock_item,source_warehouse,destination_warehouse,quantity,created_by=None,note=""):
    if source_warehouse.pk==destination_warehouse.pk: raise ValidationError({"warehouse":"Source and destination must differ."})
    if quantity<=0: raise ValidationError({"quantity":"Must be greater than zero."})
    stock_item=StockItem.objects.select_for_update().get(pk=stock_item.pk)
    stocks={s.warehouse_id:s for s in ProductStock.objects.select_for_update().filter(stock_item=stock_item,warehouse_id__in=[source_warehouse.pk,destination_warehouse.pk])}
    source=stocks.get(source_warehouse.pk)
    if not source or source.available_stock<quantity: raise ValidationError({"stock":"Insufficient source stock."})
    dest=stocks.get(destination_warehouse.pk)
    if not dest: dest=ProductStock.objects.create(stock_item=stock_item,warehouse=destination_warehouse)
    sb=source.available_stock; db=dest.available_stock; source.available_stock-=quantity; dest.available_stock+=quantity
    source.save(update_fields=["available_stock","updated_at"]); dest.save(update_fields=["available_stock","updated_at"])
    ref=f"{source.pk}:{dest.pk}:{timezone.now().timestamp()}"
    _movement(source,StockMovement.Type.TRANSFER,-quantity,sb,source.available_stock,"transfer",ref,note,created_by)
    _movement(dest,StockMovement.Type.TRANSFER,quantity,db,dest.available_stock,"transfer",ref,note,created_by)
    return source,dest

@transaction.atomic
def receive_purchase(*,purchase,receipts,user=None):
    purchase=Purchase.objects.select_for_update().get(pk=purchase.pk)
    if purchase.status==Purchase.Status.CANCELLED: raise ValidationError({"purchase":"Cancelled purchase cannot be received."})
    item_ids=[int(x["item_id"]) for x in receipts]
    items={i.id:i for i in PurchaseItem.objects.select_for_update().filter(purchase=purchase,id__in=item_ids).select_related("product","product_variant__product")}
    if len(items)!=len(set(item_ids)): raise ValidationError({"items":"Invalid purchase item."})
    for row in receipts:
        item=items[int(row["item_id"])]; qty=int(row["quantity"]); remaining=item.quantity-item.received_quantity
        if qty<=0 or qty>remaining: raise ValidationError({"quantity":f"Item {item.id} can receive at most {remaining}."})
        stock_item=resolve_stock_item(product=item.product,variant=item.product_variant)
        increase_stock(stock_item=stock_item,warehouse=purchase.warehouse,quantity=qty,movement_type=StockMovement.Type.PURCHASE,reference_type="purchase_item",reference_id=item.id,note=f"Purchase {purchase.purchase_number}",created_by=user)
        stock=ProductStock.objects.select_for_update().get(stock_item=stock_item,warehouse=purchase.warehouse)
        if stock.incoming_stock:
            stock.incoming_stock=max(0,stock.incoming_stock-qty); stock.save(update_fields=["incoming_stock","updated_at"])
        item.received_quantity+=qty; item.save(update_fields=["received_quantity","updated_at"])
    all_items=list(PurchaseItem.objects.filter(purchase=purchase).only("quantity","received_quantity"))
    purchase.status=Purchase.Status.RECEIVED if all(i.received_quantity>=i.quantity for i in all_items) else Purchase.Status.PARTIAL
    purchase.received_by=user or purchase.received_by; purchase.received_at=timezone.now() if purchase.status==Purchase.Status.RECEIVED else purchase.received_at
    purchase.save(update_fields=["status","received_by","received_at","updated_at"]); return purchase

@transaction.atomic
def approve_purchase(*,purchase,user=None):
    purchase=Purchase.objects.select_for_update().get(pk=purchase.pk)
    if purchase.status != Purchase.Status.DRAFT:
        raise ValidationError({"purchase":"Only draft purchases can be approved."})
    items=list(PurchaseItem.objects.select_for_update().filter(purchase=purchase).select_related("product","product_variant__product").order_by("id"))
    if not items: raise ValidationError({"items":"Purchase must contain at least one item."})
    for item in items:
        stock_item=resolve_stock_item(product=item.product,variant=item.product_variant)
        stock,_=ProductStock.objects.select_for_update().get_or_create(stock_item=stock_item,warehouse=purchase.warehouse)
        stock.incoming_stock += item.quantity-item.received_quantity
        stock.save(update_fields=["incoming_stock","updated_at"])
    purchase.status=Purchase.Status.APPROVED; purchase.approved_by=user; purchase.save(update_fields=["status","approved_by","updated_at"]); return purchase

@transaction.atomic
def cancel_purchase(*,purchase,user=None):
    purchase=Purchase.objects.select_for_update().get(pk=purchase.pk)
    if purchase.status not in {Purchase.Status.DRAFT,Purchase.Status.APPROVED}:
        raise ValidationError({"purchase":"Only draft or unreceived approved purchases can be cancelled."})
    items=list(PurchaseItem.objects.select_for_update().filter(purchase=purchase).select_related("product","product_variant__product").order_by("id"))
    if any(i.received_quantity for i in items): raise ValidationError({"purchase":"A partially received purchase cannot be cancelled."})
    if purchase.status==Purchase.Status.APPROVED:
        for item in items:
            stock_item=resolve_stock_item(product=item.product,variant=item.product_variant)
            stock=ProductStock.objects.select_for_update().filter(stock_item=stock_item,warehouse=purchase.warehouse).first()
            if stock:
                stock.incoming_stock=max(0,stock.incoming_stock-item.quantity); stock.save(update_fields=["incoming_stock","updated_at"])
    purchase.status=Purchase.Status.CANCELLED; purchase.save(update_fields=["status","updated_at"]); return purchase
