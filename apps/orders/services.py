from decimal import Decimal
import uuid
from django.db import transaction,IntegrityError
from django.db.models import F
from rest_framework.exceptions import APIException,ValidationError
from apps.accounts.models import User,Address
from apps.accounts.utils import normalize_phone,PhoneFormatError
from apps.accounts.serializers import jwt_for_user
from apps.carts.models import Cart,CartItem
from apps.inventory.services import resolve_stock_item,get_sellable_stock,reserve_stock,release_stock,consume_reserved_stock
from apps.promotions.models import CouponUsage,Coupon
from apps.promotions.services import validate_coupon,calculate_promotions
from apps.payments.services import create_payment
from apps.catalog.models import ProductImage
from .models import Order,OrderItem

class AccountExistsVerificationRequired(APIException):
    status_code=409; default_code="ACCOUNT_EXISTS_VERIFICATION_REQUIRED"; default_detail="An account already exists for this phone. Login or verify by OTP."

def _order_number(): return f"ORD-{uuid.uuid4().hex[:12].upper()}"
def _variant_snapshot(variant):
    if not variant:return {}
    return {v.attribute.name:v.value for v in variant.attributes.select_related("attribute").all()}
def _image_snapshot(product,variant=None):
    q=ProductImage.objects.filter(product=product)
    if variant:
        image=q.filter(variant=variant,is_primary=True).first() or q.filter(variant=variant).order_by("order").first()
        if image:return image.image.name
    image=q.filter(variant__isnull=True,is_primary=True).first() or q.filter(variant__isnull=True).order_by("order").first()
    return image.image.name if image else ""

def _prevalidate_stock(items):
    for item in items:
        si=resolve_stock_item(product=item.product,variant=item.product_variant)
        if get_sellable_stock(stock_item=si)<item.quantity: raise ValidationError({"stock":f"Insufficient stock for cart item {item.id}."})

def _address_payload(data): return {k:data[k] for k in ("name","phone","district","thana","address")}|{"label":data.get("label","")}

@transaction.atomic
def checkout(*,cart,customer_data,shipping_method,payment_method,coupon_code="",request_user=None):
    cart=Cart.objects.select_for_update().get(pk=cart.pk,is_active=True)
    items=list(CartItem.objects.select_for_update().filter(cart=cart).select_related("product__brand","product__category","product_variant__product__brand","product_variant__product__category").prefetch_related("product_variant__attributes__attribute"))
    if not items: raise ValidationError({"cart":"Cart is empty."})
    _prevalidate_stock(items)
    try: phone=normalize_phone(customer_data["phone"])
    except PhoneFormatError as exc: raise ValidationError({"phone":str(exc)})
    customer_data={**customer_data,"phone":phone}; account_created=False
    if request_user and request_user.is_authenticated:
        user=request_user
        if user.phone and user.phone!=phone: raise ValidationError({"phone":"Checkout phone must match the authenticated account phone."})
    else:
        existing=User.objects.filter(phone=phone).first()
        if existing: raise AccountExistsVerificationRequired()
        try:
            with transaction.atomic(): user=User.objects.create_user(phone=phone,full_name=customer_data["name"])
        except IntegrityError:
            raise AccountExistsVerificationRequired()
        account_created=True
    address_data=_address_payload(customer_data)
    address, _ = Address.objects.get_or_create(user=user,**address_data,defaults={"is_default":not user.addresses.exists()})
    subtotal=sum((i.line_total for i in items),Decimal("0"))
    promo=calculate_promotions(cart=cart,user=user); promo_discount=promo["discount"]
    coupon_result=None; coupon_discount=Decimal("0"); free_shipping=False
    if coupon_code:
        coupon_result=validate_coupon(code=coupon_code,cart=cart,user=user,lock=True); coupon_discount=coupon_result["discount"]; free_shipping=coupon_result["free_shipping"]
    discount=min(subtotal,promo_discount+coupon_discount)
    shipping_charge=Decimal("0") if free_shipping else Decimal(str(shipping_method.charge_for(subtotal-discount)))
    tax=Decimal("0.00"); total=max(Decimal("0"),subtotal-discount+shipping_charge+tax)
    order=Order.objects.create(order_number=_order_number(),user=user,customer_name=customer_data["name"],customer_phone=phone,shipping_address_snapshot=_address_payload(customer_data),shipping_method=shipping_method,coupon_code_snapshot=coupon_result["coupon"].code if coupon_result else "",promotion_snapshot=promo["applied"],subtotal=subtotal,discount=discount,shipping_charge=shipping_charge,tax=tax,total=total)
    for cart_item in items:
        product=cart_item.product if cart_item.product_id else cart_item.product_variant.product; variant=cart_item.product_variant
        cost=(variant.cost_price if variant and variant.cost_price is not None else product.cost_price) or Decimal("0")
        order_item=OrderItem.objects.create(order=order,product=product,variant=variant,product_name_snapshot=product.name,sku_snapshot=product.sku if cart_item.product_id else variant.sku,variant_snapshot=_variant_snapshot(variant),image_snapshot=_image_snapshot(product,variant),quantity=cart_item.quantity,unit_price=cart_item.unit_price,total=cart_item.line_total,cost_price_snapshot=cost)
        si=resolve_stock_item(product=cart_item.product,variant=cart_item.product_variant)
        reserve_stock(stock_item=si,quantity=cart_item.quantity,reference_type="order_item",reference_id=order_item.id,created_by=user if user.is_staff else None)
    payment=create_payment(order=order,method=payment_method,amount=total)
    if coupon_result:
        Coupon.objects.select_for_update().filter(pk=coupon_result["coupon"].pk).update(used_count=F("used_count")+1)
        CouponUsage.objects.create(coupon=coupon_result["coupon"],user=user,order=order)
    cart.is_active=False; cart.save(update_fields=["is_active","updated_at"])
    result={"order":order,"payment":payment,"account_created":account_created,"address":address}
    if account_created: result["auth"]=jwt_for_user(user)
    return result

TRANSITIONS={
    Order.Status.PENDING:{Order.Status.CONFIRMED,Order.Status.CANCELLED},
    Order.Status.CONFIRMED:{Order.Status.PROCESSING,Order.Status.CANCELLED},
    Order.Status.PROCESSING:{Order.Status.PACKED,Order.Status.CANCELLED},
    Order.Status.PACKED:{Order.Status.READY_TO_SHIP,Order.Status.CANCELLED},
    Order.Status.READY_TO_SHIP:{Order.Status.SHIPPED,Order.Status.CANCELLED},
    Order.Status.SHIPPED:{Order.Status.OUT_FOR_DELIVERY},
    Order.Status.OUT_FOR_DELIVERY:{Order.Status.DELIVERED},
    Order.Status.DELIVERED:{Order.Status.RETURN_REQUESTED,Order.Status.PARTIALLY_RETURNED,Order.Status.RETURNED,Order.Status.REFUNDED},
    Order.Status.RETURN_REQUESTED:{Order.Status.DELIVERED,Order.Status.PARTIALLY_RETURNED,Order.Status.RETURNED,Order.Status.REFUNDED},
    Order.Status.PARTIALLY_RETURNED:{Order.Status.RETURNED,Order.Status.REFUNDED},
    Order.Status.RETURNED:{Order.Status.REFUNDED},
    Order.Status.CANCELLED:{Order.Status.REFUNDED},
}
@transaction.atomic
def transition_order(*,order,new_status,actor=None):
    order=Order.objects.select_for_update().prefetch_related("items").get(pk=order.pk)
    if new_status==order.order_status:return order
    if new_status not in TRANSITIONS.get(order.order_status,set()): raise ValidationError({"order_status":f"Invalid transition {order.order_status} → {new_status}."})
    if new_status==Order.Status.CANCELLED:
        for item in order.items.all(): release_stock(reference_type="order_item",reference_id=item.id,created_by=actor)
    elif new_status==Order.Status.DELIVERED:
        for item in order.items.all(): consume_reserved_stock(reference_type="order_item",reference_id=item.id,created_by=actor)
        order.fulfillment_status=Order.FulfillmentStatus.FULFILLED
    elif new_status in {Order.Status.PROCESSING,Order.Status.PACKED,Order.Status.READY_TO_SHIP,Order.Status.SHIPPED,Order.Status.OUT_FOR_DELIVERY}: order.fulfillment_status=Order.FulfillmentStatus.PROCESSING
    elif new_status==Order.Status.PARTIALLY_RETURNED: order.fulfillment_status=Order.FulfillmentStatus.PARTIAL_RETURN
    elif new_status==Order.Status.RETURNED: order.fulfillment_status=Order.FulfillmentStatus.RETURNED
    order.order_status=new_status; order.save(update_fields=["order_status","fulfillment_status","updated_at"]); return order
