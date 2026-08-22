from django.db.models import Prefetch, Min, Max, Q, Sum, Value, IntegerField
from django.db.models.functions import Coalesce
from .models import Product, ProductVariant, ProductImage, ProductClaim

def product_list_queryset():
    active_variants=ProductVariant.objects.filter(is_active=True).prefetch_related("variant_attribute_values__attribute_value__attribute").annotate(available_stock=Coalesce(Sum("stock_item__stocks__available_stock"),Value(0),output_field=IntegerField()))
    return (Product.objects.filter(status=Product.Status.ACTIVE)
        .select_related("brand","category")
        .prefetch_related(Prefetch("variants",queryset=active_variants),Prefetch("images",queryset=ProductImage.objects.order_by("order")))
        .annotate(variant_min_price=Min("variants__price_override",filter=Q(variants__is_active=True)),variant_max_price=Max("variants__price_override",filter=Q(variants__is_active=True)),simple_available_stock=Coalesce(Sum("stock_item__stocks__available_stock"),Value(0),output_field=IntegerField()),variant_available_stock=Coalesce(Sum("variants__stock_item__stocks__available_stock",filter=Q(variants__is_active=True)),Value(0),output_field=IntegerField())))

def product_detail_queryset():
    return product_list_queryset().prefetch_related("beauty_profile__skin_types","beauty_profile__hair_types","beauty_profile__concerns","beauty_profile__ingredients","product_claims__claim")
