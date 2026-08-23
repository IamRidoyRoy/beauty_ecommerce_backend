from datetime import timedelta, datetime, time
from decimal import Decimal
from django.db.models import Sum,Count,Avg,F,Q,Case,When,Value,DecimalField,IntegerField,ExpressionWrapper,Exists,OuterRef,Subquery,Min
from django.db.models.functions import TruncDate,Coalesce
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date
from apps.orders.models import Order,OrderItem
from apps.catalog.models import Product,Category,Brand
from apps.inventory.models import ProductStock,StockMovement
from apps.accounts.models import User,UserRole
from apps.payments.models import Payment
from apps.returns.models import ReturnRequest,Refund
from apps.promotions.models import Coupon,CouponUsage
from apps.common.models import AnalyticsEvent

def _range(params):
    end=timezone.now(); start=None
    raw_start=params.get("start") or params.get("date_from"); raw_end=params.get("end") or params.get("date_to")
    if raw_start:
        parsed=parse_datetime(str(raw_start))
        if parsed is None:
            d=parse_date(str(raw_start)); parsed=timezone.make_aware(datetime.combine(d,time.min)) if d else None
        start=parsed
    if raw_end:
        parsed=parse_datetime(str(raw_end))
        if parsed is None:
            d=parse_date(str(raw_end)); parsed=timezone.make_aware(datetime.combine(d,time.max)) if d else None
        if parsed: end=parsed
    if start is None: start=end-timedelta(days=int(params.get("days",30) or 30))
    return start,end

def dashboard(params):
    start,end=_range(params); orders=Order.objects.filter(created_at__range=(start,end)); valid=orders.exclude(order_status=Order.Status.CANCELLED); paid=valid.filter(payment_status=Order.PaymentStatus.PAID)
    item_qs=OrderItem.objects.filter(order__in=valid)
    revenue=paid.aggregate(v=Coalesce(Sum("total"),Decimal("0")))["v"]
    aov=paid.aggregate(v=Coalesce(Avg("total"),Decimal("0")))["v"]
    units=item_qs.aggregate(v=Coalesce(Sum("quantity"),0))["v"]
    cogs=item_qs.aggregate(v=Coalesce(Sum(ExpressionWrapper(F("cost_price_snapshot")*F("quantity"),output_field=DecimalField(max_digits=18,decimal_places=2))),Decimal("0")))["v"]
    discounts=valid.aggregate(v=Coalesce(Sum("discount"),Decimal("0")))["v"]
    product_revenue=item_qs.aggregate(v=Coalesce(Sum("total"),Decimal("0")))["v"]
    refund_impact=Refund.objects.filter(status=Refund.Status.COMPLETED,created_at__range=(start,end)).aggregate(v=Coalesce(Sum("amount"),Decimal("0")))["v"]
    gross_profit=product_revenue-discounts-cogs-refund_impact
    return {"orders":orders.count(),"revenue":revenue,"aov":aov,"units_sold":units,"gross_profit":gross_profit,"customers":User.objects.filter(role=UserRole.CUSTOMER,created_at__range=(start,end)).count(),"pending_orders":Order.objects.filter(order_status=Order.Status.PENDING).count(),"return_requests":ReturnRequest.objects.filter(status=ReturnRequest.Status.REQUESTED).count(),"low_stock_rows":ProductStock.objects.filter(available_stock__lte=F("low_stock_threshold"),available_stock__gt=0).count(),"out_of_stock_rows":ProductStock.objects.filter(available_stock__lte=0).count()}
def sales(params):
    start,end=_range(params); return list(Order.objects.filter(created_at__range=(start,end)).exclude(order_status=Order.Status.CANCELLED).annotate(day=TruncDate("created_at")).values("day").annotate(orders=Count("id"),sales=Sum("total"),discount=Sum("discount"),shipping=Sum("shipping_charge"),tax=Sum("tax")).order_by("day"))
def orders(params):
    start,end=_range(params); return list(Order.objects.filter(created_at__range=(start,end)).values("order_status").annotate(count=Count("id"),value=Sum("total")).order_by("order_status"))
def product_performance(params):
    start,end=_range(params); return list(OrderItem.objects.filter(order__created_at__range=(start,end)).exclude(order__order_status=Order.Status.CANCELLED).values("product_id","product_name_snapshot").annotate(units=Sum("quantity"),revenue=Sum("total"),avg_price=Avg("unit_price"),orders=Count("order_id",distinct=True)).order_by("-revenue")[:200])
def category_performance(params):
    start,end=_range(params); return list(OrderItem.objects.filter(order__created_at__range=(start,end)).exclude(order__order_status=Order.Status.CANCELLED).values("product__category__id","product__category__name").annotate(units=Sum("quantity"),revenue=Sum("total"),orders=Count("order_id",distinct=True)).order_by("-revenue"))
def brand_performance(params):
    start,end=_range(params); return list(OrderItem.objects.filter(order__created_at__range=(start,end)).exclude(order__order_status=Order.Status.CANCELLED).values("product__brand__id","product__brand__name").annotate(units=Sum("quantity"),revenue=Sum("total"),orders=Count("order_id",distinct=True)).order_by("-revenue"))
def inventory(params):
    return list(ProductStock.objects.select_related("stock_item__product","stock_item__variant__product","warehouse").values("stock_item_id","warehouse__name","stock_item__product__name","stock_item__product__sku","stock_item__variant__product__name","stock_item__variant__sku").annotate(available=Sum("available_stock"),reserved=Sum("reserved_stock"),damaged=Sum("damaged_stock"),incoming=Sum("incoming_stock")).order_by("available")[:500])
def stock_aging(params):
    first_in=StockMovement.objects.filter(stock_item=OuterRef("stock_item"),warehouse=OuterRef("warehouse"),movement_type__in=[StockMovement.Type.PURCHASE,StockMovement.Type.RESTOCK],quantity__gt=0).order_by("created_at").values("created_at")[:1]
    return list(ProductStock.objects.filter(available_stock__gt=0).annotate(first_stocked_at=Subquery(first_in)).values("stock_item_id","warehouse__name","available_stock","first_stocked_at").order_by("first_stocked_at")[:500])
def dead_stock(params):
    start,end=_range(params)
    recent_sale=OrderItem.objects.filter(Q(product_id=OuterRef("stock_item__product_id"))|Q(variant_id=OuterRef("stock_item__variant_id")),order__created_at__range=(start,end)).exclude(order__order_status=Order.Status.CANCELLED)
    return list(ProductStock.objects.filter(available_stock__gt=0).annotate(has_recent_sale=Exists(recent_sale)).filter(has_recent_sale=False).values("stock_item__product__id","stock_item__product__name","stock_item__variant__id","stock_item__variant__sku","stock_item__variant__product__name","available_stock","warehouse__name")[:500])
def low_performing(params):
    start,end=_range(params); return list(Product.objects.filter(status=Product.Status.ACTIVE).annotate(units=Coalesce(Sum("order_items__quantity",filter=Q(order_items__order__created_at__range=(start,end))&~Q(order_items__order__order_status=Order.Status.CANCELLED)),0)).values("id","name","sku","units").order_by("units","name")[:100])
def best_sellers(params): return product_performance(params)[:50]
def customers(params):
    start,end=_range(params); return list(User.objects.filter(role=UserRole.CUSTOMER).annotate(order_count=Count("orders",filter=Q(orders__created_at__range=(start,end))),lifetime_value=Coalesce(Sum("orders__total",filter=~Q(orders__order_status=Order.Status.CANCELLED)),Decimal("0"))).values("id","full_name","phone","created_at","order_count","lifetime_value").order_by("-lifetime_value")[:500])
def customer_lifetime_value(params): return customers(params)
def payments(params):
    start,end=_range(params); return list(Payment.objects.filter(created_at__range=(start,end)).values("method","status").annotate(count=Count("id"),amount=Sum("amount")).order_by("method","status"))
def returns(params):
    start,end=_range(params); return list(ReturnRequest.objects.filter(created_at__range=(start,end)).values("status").annotate(count=Count("id"),items=Count("items"),units=Sum("items__quantity")))
def refunds(params):
    start,end=_range(params); return list(Refund.objects.filter(created_at__range=(start,end)).values("status").annotate(count=Count("id"),amount=Sum("amount")))
def discounts(params):
    start,end=_range(params); return Order.objects.filter(created_at__range=(start,end)).aggregate(total_discount=Coalesce(Sum("discount"),Decimal("0")),orders_with_discount=Count("id",filter=Q(discount__gt=0)))
def coupon_performance(params):
    start,end=_range(params); period=Q(usages__order__created_at__range=(start,end))
    return list(Coupon.objects.annotate(orders=Count("usages",filter=period),revenue=Coalesce(Sum("usages__order__total",filter=period),Decimal("0")),discount=Coalesce(Sum("usages__order__discount",filter=period),Decimal("0"))).values("id","code","coupon_type","orders","revenue","discount","used_count").order_by("-orders"))
def sales_geography(params):
    start,end=_range(params); return list(Order.objects.filter(created_at__range=(start,end)).exclude(order_status=Order.Status.CANCELLED).values(district=models_json_key("shipping_address_snapshot","district")).annotate(orders=Count("id"),sales=Sum("total")).order_by("-sales"))
def models_json_key(field,key):
    from django.db.models.fields.json import KeyTextTransform
    return KeyTextTransform(key,field)
def funnel(params):
    start,end=_range(params); counts={row["event_type"]:row["count"] for row in AnalyticsEvent.objects.filter(created_at__range=(start,end)).values("event_type").annotate(count=Count("id"))}; return {k:counts.get(k,0) for k in ["product_view","add_to_cart","wishlist","checkout_started","order_completed"]}
def profit(params):
    start,end=_range(params); valid=~Q(order__order_status=Order.Status.CANCELLED)
    item_fin=OrderItem.objects.filter(order__created_at__range=(start,end)).exclude(order__order_status=Order.Status.CANCELLED).aggregate(product_revenue=Coalesce(Sum("total"),Decimal("0")),cogs=Coalesce(Sum(ExpressionWrapper(F("cost_price_snapshot")*F("quantity"),output_field=DecimalField(max_digits=18,decimal_places=2))),Decimal("0")))
    order_fin=Order.objects.filter(created_at__range=(start,end)).exclude(order_status=Order.Status.CANCELLED).aggregate(discounts=Coalesce(Sum("discount"),Decimal("0")))
    refund_total=Refund.objects.filter(status=Refund.Status.COMPLETED,created_at__range=(start,end)).aggregate(v=Coalesce(Sum("amount"),Decimal("0")))["v"]
    net=item_fin["product_revenue"]-order_fin["discounts"]; gross=net-item_fin["cogs"]-refund_total
    return {"product_revenue":item_fin["product_revenue"],"discounts":order_fin["discounts"],"net_product_revenue":net,"cogs":item_fin["cogs"],"refund_impact":refund_total,"gross_profit":gross,"margin_percentage":(gross/net*Decimal("100")) if net else Decimal("0")}
REPORTS={"sales":sales,"orders":orders,"product-performance":product_performance,"category-performance":category_performance,"brand-performance":brand_performance,"inventory":inventory,"stock-aging":stock_aging,"dead-stock":dead_stock,"low-performing-products":low_performing,"best-sellers":best_sellers,"customers":customers,"customer-lifetime-value":customer_lifetime_value,"payments":payments,"returns":returns,"refunds":refunds,"discounts":discounts,"coupon-performance":coupon_performance,"sales-geography":sales_geography,"funnel":funnel,"profit":profit}
