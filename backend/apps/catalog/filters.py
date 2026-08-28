import django_filters
from .models import Product
class ProductFilter(django_filters.FilterSet):
    min_price=django_filters.NumberFilter(field_name="base_price",lookup_expr="gte")
    max_price=django_filters.NumberFilter(field_name="base_price",lookup_expr="lte")
    brand=django_filters.CharFilter(field_name="brand__slug")
    category=django_filters.CharFilter(field_name="category__slug")
    concern=django_filters.CharFilter(field_name="beauty_profile__concerns__slug")
    skin_type=django_filters.CharFilter(field_name="beauty_profile__skin_types__slug")
    class Meta: model=Product; fields=("product_type","featured","new_arrival","bestseller","trending")
