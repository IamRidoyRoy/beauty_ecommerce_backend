from decimal import Decimal
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import Coupon,Promotion

def _cart_subtotal(cart): return sum((i.line_total for i in cart.items.select_related("product","product_variant__product").all()),Decimal("0"))
def _eligible_subtotal(coupon,cart):
    items=list(cart.items.select_related("product","product_variant__product").all()); product_ids=set(coupon.products.values_list("id",flat=True)); brand_ids=set(coupon.brands.values_list("id",flat=True)); category_ids=set(coupon.categories.values_list("id",flat=True))
    restricted=bool(product_ids or brand_ids or category_ids); total=Decimal("0")
    for i in items:
        p=i.product if i.product_id else i.product_variant.product
        if not restricted or p.id in product_ids or p.brand_id in brand_ids or p.category_id in category_ids: total+=i.line_total
    return total

def validate_coupon(*,code,cart,user=None,lock=False):
    now=timezone.now(); qs=Coupon.objects.prefetch_related("products","brands","categories","customers"); qs=qs.select_for_update() if lock else qs; coupon=qs.filter(code__iexact=code,active=True).first()
    if not coupon: raise ValidationError({"coupon_code":"Invalid coupon."})
    if coupon.starts_at and coupon.starts_at>now or coupon.ends_at and coupon.ends_at<now: raise ValidationError({"coupon_code":"Coupon is not active."})
    subtotal=_cart_subtotal(cart)
    if subtotal<coupon.minimum_spend: raise ValidationError({"coupon_code":f"Minimum spend is {coupon.minimum_spend}."})
    if coupon.usage_limit is not None and coupon.used_count>=coupon.usage_limit: raise ValidationError({"coupon_code":"Coupon usage limit reached."})
    customer_ids=set(coupon.customers.values_list("id",flat=True))
    if customer_ids and (not user or user.id not in customer_ids): raise ValidationError({"coupon_code":"Coupon is not available for this customer."})
    if user and coupon.usage_limit_per_customer is not None and coupon.usages.filter(user=user).count()>=coupon.usage_limit_per_customer: raise ValidationError({"coupon_code":"Customer usage limit reached."})
    if coupon.first_order_only and user:
        from apps.orders.models import Order
        if Order.objects.filter(user=user).exclude(order_status=Order.Status.CANCELLED).exists(): raise ValidationError({"coupon_code":"Coupon is for first orders only."})
    eligible=_eligible_subtotal(coupon,cart)
    if coupon.coupon_type==Coupon.Type.PERCENTAGE: discount=(eligible*coupon.value/Decimal("100")).quantize(Decimal("0.01"))
    elif coupon.coupon_type==Coupon.Type.FIXED: discount=min(coupon.value,eligible)
    else: discount=Decimal("0")
    if coupon.max_discount is not None: discount=min(discount,coupon.max_discount)
    return {"coupon":coupon,"discount":discount,"free_shipping":coupon.coupon_type==Coupon.Type.FREE_SHIPPING,"eligible_subtotal":eligible}

def calculate_promotions(*,cart,user=None):
    now=timezone.now(); qs=Promotion.objects.filter(active=True).filter(Q(starts_at__isnull=True)|Q(starts_at__lte=now)).filter(Q(ends_at__isnull=True)|Q(ends_at__gte=now)).prefetch_related("products","brands","categories").order_by("priority")
    items=list(cart.items.select_related("product","product_variant__product")); total=Decimal("0"); applied=[]
    for promo in qs:
        cfg=promo.config or {}; kind=promo.promotion_type; discount=Decimal("0")
        percent=Decimal(str(cfg.get("percent",0))); fixed=Decimal(str(cfg.get("fixed",0))); minimum=Decimal(str(cfg.get("minimum_spend",0)))
        subtotal=sum((i.line_total for i in items),Decimal("0"))
        if kind==Promotion.Type.ORDER_VALUE and subtotal>=minimum: discount=fixed or (subtotal*percent/Decimal("100"))
        elif kind==Promotion.Type.FIRST_ORDER and user:
            from apps.orders.models import Order
            if not Order.objects.filter(user=user).exists(): discount=fixed or (subtotal*percent/Decimal("100"))
        elif kind in {Promotion.Type.BRAND,Promotion.Type.CATEGORY,Promotion.Type.PRODUCT,Promotion.Type.FLASH}:
            pids=set(promo.products.values_list("id",flat=True)); bids=set(promo.brands.values_list("id",flat=True)); cids=set(promo.categories.values_list("id",flat=True)); eligible=Decimal("0")
            for i in items:
                p=i.product if i.product_id else i.product_variant.product
                if kind==Promotion.Type.FLASH or p.id in pids or p.brand_id in bids or p.category_id in cids: eligible+=i.line_total
            discount=fixed or (eligible*percent/Decimal("100"))
        elif kind in {Promotion.Type.BOGO,Promotion.Type.BUY_X_GET_Y}:
            buy=int(cfg.get("buy",1)); get=int(cfg.get("get",1)); eligible_ids=set(promo.products.values_list("id",flat=True));
            for i in items:
                p=i.product if i.product_id else i.product_variant.product
                if not eligible_ids or p.id in eligible_ids:
                    free_units=(i.quantity//(buy+get))*get; discount += i.unit_price*free_units
        discount=discount.quantize(Decimal("0.01"))
        if discount>0:
            total+=discount; applied.append({"id":promo.id,"name":promo.name,"discount":str(discount)})
            if not promo.combinable: break
    return {"discount":min(total,sum((i.line_total for i in items),Decimal("0"))),"applied":applied}
