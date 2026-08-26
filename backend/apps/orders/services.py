from decimal import Decimal
import uuid

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from rest_framework.exceptions import ValidationError

from apps.accounts.models import Address, User
from apps.accounts.serializers import jwt_for_user
from apps.accounts.utils import PhoneFormatError, normalize_phone
from apps.carts.models import Cart, CartItem
from apps.carts.services import add_cart_item
from apps.common.models import CheckoutSettings
from apps.catalog.models import ProductImage
from apps.delivery.services import resolve_delivery_quote
from apps.inventory.services import consume_reserved_stock, get_sellable_stock, release_stock, reserve_stock, resolve_stock_item
from apps.payments.services import create_payment
from apps.promotions.models import Coupon, CouponUsage
from apps.promotions.services import calculate_promotions, validate_coupon

from .models import Order, OrderItem


def _order_number():
    return f"ORD-{uuid.uuid4().hex[:12].upper()}"


def _variant_snapshot(variant):
    if not variant:
        return {}
    return {v.attribute.name: v.value for v in variant.attributes.select_related("attribute").all()}


def _image_snapshot(product, variant=None):
    q = ProductImage.objects.filter(product=product)
    if variant:
        image = q.filter(variant=variant, is_primary=True).first() or q.filter(variant=variant).order_by("order").first()
        if image:
            return image.image.url
    image = q.filter(variant__isnull=True, is_primary=True).first() or q.filter(variant__isnull=True).order_by("order").first()
    return image.image.url if image else ""


def _prevalidate_stock(items):
    for item in items:
        si = resolve_stock_item(product=item.product, variant=item.product_variant)
        if get_sellable_stock(stock_item=si) < item.quantity:
            raise ValidationError({"stock": f"Insufficient stock for cart item {item.id}."})


def _address_payload(data, quote):
    return {
        "name": data["name"],
        "phone": data["phone"],
        "district": quote.district.name,
        "district_id": quote.district.id,
        "thana": quote.thana.name,
        "thana_id": quote.thana.id,
        "address": data["address"],
        "label": data.get("label", ""),
        "delivery_module": {
            "id": quote.module.id,
            "code": quote.module.code,
            "name": quote.module.name,
            "charge": str(quote.charge),
        },
    }


@transaction.atomic
def checkout(*, cart, customer_data, shipping_method, payment_method, coupon_code="", request_user=None, order_note="", actor=None):
    cart = Cart.objects.select_for_update().get(pk=cart.pk, is_active=True)
    items = list(
        CartItem.objects.select_for_update()
        .filter(cart=cart)
        .select_related(
            "product__brand", "product__category",
            "product_variant__product__brand", "product_variant__product__category",
        )
        .prefetch_related("product_variant__attributes__attribute")
    )
    if not items:
        raise ValidationError({"cart": "Cart is empty."})
    _prevalidate_stock(items)

    try:
        phone = normalize_phone(customer_data["phone"])
    except PhoneFormatError as exc:
        raise ValidationError({"phone": str(exc)})

    district = customer_data["district"]
    thana = customer_data["thana"]
    quote = resolve_delivery_quote(district=district, thana=thana)
    customer_data = {**customer_data, "phone": phone}

    account_created = False
    existing_account = False
    verification_required = False
    save_address_to_account = False

    if request_user and request_user.is_authenticated:
        user = request_user
        if user.phone and user.phone != phone:
            raise ValidationError({"phone": "Checkout phone must match the authenticated account phone."})
        save_address_to_account = True
    else:
        # Business rule: an existing phone must NOT block guest checkout.
        # We attach the order to the existing account for order history, but we
        # never issue JWTs or modify that account's saved addresses unless the
        # customer has authenticated.
        existing = User.objects.filter(phone=phone).first()
        if existing:
            user = existing
            existing_account = True
        else:
            try:
                with transaction.atomic():
                    user = User.objects.create_user(phone=phone, full_name=customer_data["name"])
            except IntegrityError:
                # A concurrent checkout may have created the phone first.
                user = User.objects.select_for_update().get(phone=phone)
                existing_account = True
            else:
                account_created = True
                save_address_to_account = True

    address_snapshot = _address_payload(customer_data, quote)
    address = None
    if save_address_to_account:
        address_defaults = {"is_default": not user.addresses.exists()}
        address, _ = Address.objects.get_or_create(
            user=user,
            name=customer_data["name"],
            phone=phone,
            district=quote.district.name,
            thana=quote.thana.name,
            address=customer_data["address"],
            label=customer_data.get("label", ""),
            defaults=address_defaults,
        )

    subtotal = sum((i.line_total for i in items), Decimal("0"))
    promo = calculate_promotions(cart=cart, user=user)
    promo_discount = promo["discount"]
    coupon_result = None
    coupon_discount = Decimal("0")
    free_shipping = False
    if coupon_code:
        coupon_result = validate_coupon(code=coupon_code, cart=cart, user=user, lock=True)
        coupon_discount = coupon_result["discount"]
        free_shipping = coupon_result["free_shipping"]

    discount = min(subtotal, promo_discount + coupon_discount)
    net_subtotal = subtotal - discount
    threshold_free = bool(
        shipping_method
        and shipping_method.free_threshold is not None
        and net_subtotal >= shipping_method.free_threshold
    )
    shipping_charge = Decimal("0") if (free_shipping or threshold_free) else quote.charge
    tax = Decimal("0.00")
    total = max(Decimal("0"), subtotal - discount + shipping_charge + tax)

    discount_snapshot = list(promo["applied"])
    if coupon_result:
        discount_snapshot.append({
            "type": "coupon",
            "code": coupon_result["coupon"].code,
            "name": f"Coupon {coupon_result['coupon'].code}",
            "discount": str(coupon_discount),
            "free_shipping": bool(free_shipping),
        })

    order = Order.objects.create(
        order_number=_order_number(),
        user=user,
        customer_name=customer_data["name"],
        customer_phone=phone,
        shipping_address_snapshot=address_snapshot,
        shipping_method=shipping_method,
        coupon_code_snapshot=coupon_result["coupon"].code if coupon_result else "",
        promotion_snapshot=discount_snapshot,
        subtotal=subtotal,
        discount=discount,
        shipping_charge=shipping_charge,
        tax=tax,
        total=total,
        notes=order_note,
    )

    for cart_item in items:
        product = cart_item.product if cart_item.product_id else cart_item.product_variant.product
        variant = cart_item.product_variant
        cost = (variant.cost_price if variant and variant.cost_price is not None else product.cost_price) or Decimal("0")
        order_item = OrderItem.objects.create(
            order=order,
            product=product,
            variant=variant,
            product_name_snapshot=product.name,
            sku_snapshot=product.sku if cart_item.product_id else variant.sku,
            variant_snapshot=_variant_snapshot(variant),
            image_snapshot=_image_snapshot(product, variant),
            quantity=cart_item.quantity,
            unit_price=cart_item.unit_price,
            total=cart_item.line_total,
            cost_price_snapshot=cost,
        )
        si = resolve_stock_item(product=cart_item.product, variant=cart_item.product_variant)
        reserve_stock(
            stock_item=si,
            quantity=cart_item.quantity,
            reference_type="order_item",
            reference_id=order_item.id,
            created_by=actor or (user if user.is_staff else None),
        )

    payment = create_payment(order=order, method=payment_method, amount=total)
    if coupon_result:
        Coupon.objects.select_for_update().filter(pk=coupon_result["coupon"].pk).update(used_count=F("used_count") + 1)
        CouponUsage.objects.create(coupon=coupon_result["coupon"], user=user, order=order)

    cart.is_active = False
    cart.save(update_fields=["is_active", "updated_at"])

    if existing_account and not (request_user and request_user.is_authenticated):
        checkout_settings = CheckoutSettings.current()
        verification_required = (
            checkout_settings.existing_customer_otp_verification
            if checkout_settings is not None
            else True
        )

    result = {
        "order": order,
        "payment": payment,
        "account_created": account_created,
        "existing_account": existing_account,
        "verification_required": verification_required,
        "address": address,
        "delivery": {
            "module": quote.module.code,
            "module_name": quote.module.name,
            "charge": str(shipping_charge),
            "base_area_charge": str(quote.charge),
        },
    }
    if account_created:
        result["auth"] = jwt_for_user(user)
    elif existing_account and not verification_required:
        # Development/test-only bypass. Production settings force this off.
        if settings.DEBUG and getattr(settings, "ALLOW_INSECURE_EXISTING_CUSTOMER_AUTO_LOGIN", False):
            result["auth"] = jwt_for_user(user)
            result["verification_bypassed"] = True
    return result



@transaction.atomic
def preview_admin_order_coupon(*, items, code, phone=""):
    """Validate an admin-entered coupon against the exact draft order items.

    This creates a short-lived isolated cart so the same coupon and automatic
    promotion services used at checkout remain the single source of truth.
    Nothing is reserved, no usage is consumed, and the cart is always deleted.
    """
    cart = Cart.objects.create()
    try:
        for row in items:
            product = row["product"]
            variant = row.get("product_variant")
            add_cart_item(
                cart=cart,
                product=product if product.product_type == product.ProductType.SIMPLE else None,
                product_variant=variant if product.product_type == product.ProductType.VARIABLE else None,
                quantity=row["quantity"],
            )

        user = None
        if phone:
            try:
                normalized_phone = normalize_phone(phone)
            except PhoneFormatError as exc:
                raise ValidationError({"phone": str(exc)})
            user = User.objects.filter(phone=normalized_phone).first()

        subtotal = sum((item.line_total for item in cart.items.select_related("product", "product_variant__product")), Decimal("0"))
        promo = calculate_promotions(cart=cart, user=user)
        coupon_result = validate_coupon(code=code.strip(), cart=cart, user=user)
        coupon_discount = coupon_result["discount"]
        promotion_discount = promo["discount"]
        total_discount = min(subtotal, coupon_discount + promotion_discount)

        coupon = coupon_result["coupon"]
        return {
            "code": coupon.code,
            "coupon_type": coupon.coupon_type,
            "coupon_value": str(coupon.value),
            "subtotal": str(subtotal),
            "eligible_subtotal": str(coupon_result["eligible_subtotal"]),
            "coupon_discount": str(coupon_discount),
            "promotion_discount": str(promotion_discount),
            "total_discount": str(total_discount),
            "estimated_product_total": str(max(Decimal("0"), subtotal - total_discount)),
            "free_shipping": coupon_result["free_shipping"],
            "automatic_promotions": promo["applied"],
        }
    finally:
        Cart.objects.filter(pk=cart.pk).delete()

@transaction.atomic
def create_admin_order(*, items, customer_data, shipping_method, payment_method, coupon_code="", order_note="", actor=None):
    """Create an order from the management dashboard without touching a customer's active cart.

    The dashboard supplies the same native inventory targets used by storefront carts.
    A short-lived isolated cart is created only so the existing checkout service remains
    the single source of truth for stock validation/reservation, promotions, delivery
    pricing, snapshots, payments, and account creation/attachment.
    """
    cart = Cart.objects.create()
    for row in items:
        product = row["product"]
        variant = row.get("product_variant")
        add_cart_item(
            cart=cart,
            product=product if product.product_type == product.ProductType.SIMPLE else None,
            product_variant=variant if product.product_type == product.ProductType.VARIABLE else None,
            quantity=row["quantity"],
        )
    return checkout(
        cart=cart,
        customer_data=customer_data,
        shipping_method=shipping_method,
        payment_method=payment_method,
        coupon_code=coupon_code,
        request_user=None,
        order_note=order_note,
        actor=actor,
    )

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

# Main operational lifecycle used by the management dashboard status selector.
# Staff may choose a later state directly; the service still applies every
# intermediate transition so inventory/fulfilment side effects are preserved.
ORDER_LIFECYCLE=(
    Order.Status.PENDING,
    Order.Status.CONFIRMED,
    Order.Status.PROCESSING,
    Order.Status.PACKED,
    Order.Status.READY_TO_SHIP,
    Order.Status.SHIPPED,
    Order.Status.OUT_FOR_DELIVERY,
    Order.Status.DELIVERED,
)


def _apply_order_status(*,order,new_status,actor=None):
    if new_status==Order.Status.CANCELLED:
        for item in order.items.all():
            release_stock(reference_type="order_item",reference_id=item.id,created_by=actor)
    elif new_status==Order.Status.DELIVERED:
        for item in order.items.all():
            consume_reserved_stock(reference_type="order_item",reference_id=item.id,created_by=actor)
        order.fulfillment_status=Order.FulfillmentStatus.FULFILLED
    elif new_status in {
        Order.Status.PROCESSING,
        Order.Status.PACKED,
        Order.Status.READY_TO_SHIP,
        Order.Status.SHIPPED,
        Order.Status.OUT_FOR_DELIVERY,
    }:
        order.fulfillment_status=Order.FulfillmentStatus.PROCESSING
    elif new_status==Order.Status.PARTIALLY_RETURNED:
        order.fulfillment_status=Order.FulfillmentStatus.PARTIAL_RETURN
    elif new_status==Order.Status.RETURNED:
        order.fulfillment_status=Order.FulfillmentStatus.RETURNED
    order.order_status=new_status


@transaction.atomic
def transition_order(*,order,new_status,actor=None):
    """Strict one-step transition used by internal business workflows/tests."""
    order=Order.objects.select_for_update().prefetch_related("items").get(pk=order.pk)
    if new_status==order.order_status:
        return order
    if new_status not in TRANSITIONS.get(order.order_status,set()):
        raise ValidationError({"order_status":f"Invalid transition {order.order_status} → {new_status}."})
    _apply_order_status(order=order,new_status=new_status,actor=actor)
    order.save(update_fields=["order_status","fulfillment_status","updated_at"])
    return order


@transaction.atomic
def transition_order_to_status(*,order,new_status,actor=None):
    """
    Management transition that can move an order forward multiple lifecycle
    steps while still executing every intermediate side effect atomically.

    Example: confirmed -> delivered executes processing -> packed ->
    ready_to_ship -> shipped -> out_for_delivery -> delivered internally.
    """
    order=Order.objects.select_for_update().prefetch_related("items").get(pk=order.pk)
    if new_status==order.order_status:
        return order

    # Cancellation remains a direct controlled transition and is only allowed
    # while the strict transition map permits it.
    if new_status==Order.Status.CANCELLED:
        if new_status not in TRANSITIONS.get(order.order_status,set()):
            raise ValidationError({"order_status":f"Invalid transition {order.order_status} → {new_status}."})
        _apply_order_status(order=order,new_status=new_status,actor=actor)
        order.save(update_fields=["order_status","fulfillment_status","updated_at"])
        return order

    if order.order_status not in ORDER_LIFECYCLE or new_status not in ORDER_LIFECYCLE:
        raise ValidationError({"order_status":"This status must be changed through its dedicated return/refund workflow."})

    current_index=ORDER_LIFECYCLE.index(order.order_status)
    target_index=ORDER_LIFECYCLE.index(new_status)
    if target_index<current_index:
        raise ValidationError({"order_status":"Backward order status changes are not allowed."})

    for step_status in ORDER_LIFECYCLE[current_index+1:target_index+1]:
        if step_status not in TRANSITIONS.get(order.order_status,set()):
            raise ValidationError({"order_status":f"Invalid transition {order.order_status} → {step_status}."})
        _apply_order_status(order=order,new_status=step_status,actor=actor)

    order.save(update_fields=["order_status","fulfillment_status","updated_at"])
    return order
