import uuid
from django.db import transaction,IntegrityError
from rest_framework.exceptions import ValidationError
from .models import Cart,CartItem
from apps.catalog.models import Product,ProductVariant
from apps.inventory.services import resolve_stock_item,get_sellable_stock

def get_request_cart(request,create=True):
    """Resolve the active cart for the current request.

    Guest cart tokens are a convenience/session identifier, not
    authentication.  Browser storage can legitimately outlive a guest cart
    row (database reset, cart cleanup, expired/merged cart, etc.).  For any
    operation that is allowed to create a cart, recover transparently by
    creating a fresh guest cart instead of failing the storefront with
    ``Cart not found``.
    """
    if request.user.is_authenticated:
        cart=Cart.objects.filter(user=request.user,is_active=True).first()
        if cart or not create:return cart
        try:return Cart.objects.create(user=request.user)
        except IntegrityError:return Cart.objects.get(user=request.user,is_active=True)

    raw=request.headers.get("X-Cart-Token")
    if raw:
        try:
            token=uuid.UUID(raw)
        except (ValueError, TypeError, AttributeError):
            return Cart.objects.create() if create else None

        cart=Cart.objects.filter(token=token,user__isnull=True,is_active=True).first()
        if cart:return cart

        # A stale anonymous token must never block normal shopping.  The new
        # token is returned by CartSerializer / add-to-cart and the frontend
        # persists it for subsequent requests.
        return Cart.objects.create() if create else None

    return Cart.objects.create() if create else None

def validate_inventory_target(*,product=None,product_variant=None):
    if bool(product)==bool(product_variant): raise ValidationError({"item":"Exactly one of product or product_variant is required."})
    if product:
        if product.product_type!=Product.ProductType.SIMPLE: raise ValidationError({"product_variant":"This is a variable product; select a variant."})
        if product.status!=Product.Status.ACTIVE: raise ValidationError({"product":"Product is unavailable."})
    else:
        if product_variant.product.product_type!=Product.ProductType.VARIABLE: raise ValidationError({"product_variant":"Invalid variant."})
        if not product_variant.is_active or product_variant.product.status!=Product.Status.ACTIVE: raise ValidationError({"product_variant":"Variant is unavailable."})
    return resolve_stock_item(product=product,variant=product_variant)

@transaction.atomic
def add_cart_item(*,cart,product=None,product_variant=None,quantity=1):
    if quantity<=0: raise ValidationError({"quantity":"Must be greater than zero."})
    cart=Cart.objects.select_for_update().get(pk=cart.pk,is_active=True)
    stock_item=validate_inventory_target(product=product,product_variant=product_variant)
    lookup={"cart":cart,"product":product} if product else {"cart":cart,"product_variant":product_variant}
    item=CartItem.objects.select_for_update().filter(**lookup).first(); desired=quantity+(item.quantity if item else 0)
    if get_sellable_stock(stock_item=stock_item)<desired: raise ValidationError({"quantity":"Requested quantity exceeds available stock."})
    if item: item.quantity=desired; item.save(update_fields=["quantity","updated_at"])
    else: item=CartItem.objects.create(quantity=quantity,**lookup)
    return item

@transaction.atomic
def update_cart_item(*,item,quantity):
    Cart.objects.select_for_update().get(pk=item.cart_id,is_active=True)
    item=CartItem.objects.select_for_update().select_related("product","product_variant__product").get(pk=item.pk)
    if quantity<=0: raise ValidationError({"quantity":"Must be greater than zero."})
    stock_item=validate_inventory_target(product=item.product,product_variant=item.product_variant)
    if get_sellable_stock(stock_item=stock_item)<quantity: raise ValidationError({"quantity":"Requested quantity exceeds available stock."})
    item.quantity=quantity; item.save(update_fields=["quantity","updated_at"]); return item

@transaction.atomic
def remove_cart_item(*,item):
    Cart.objects.select_for_update().get(pk=item.cart_id,is_active=True)
    CartItem.objects.select_for_update().filter(pk=item.pk).delete()

def cart_queryset(): return Cart.objects.prefetch_related("items__product__images","items__product_variant__product__images","items__product_variant__attributes__attribute")
