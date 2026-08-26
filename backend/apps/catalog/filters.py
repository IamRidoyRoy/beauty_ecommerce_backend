import django_filters
from .models import Category, Product


class ProductFilter(django_filters.FilterSet):
    min_price = django_filters.NumberFilter(field_name="base_price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="base_price", lookup_expr="lte")
    brand = django_filters.CharFilter(field_name="brand__slug")
    category = django_filters.CharFilter(method="filter_category")
    concern = django_filters.CharFilter(field_name="beauty_profile__concerns__slug")
    skin_type = django_filters.CharFilter(field_name="beauty_profile__skin_types__slug")

    def filter_category(self, queryset, name, value):
        """
        Selecting a parent category should include products assigned to any
        active descendant category as well. Category trees are intentionally
        small, so loading the active id/parent/slug rows once is cheaper and
        avoids a recursive query per hierarchy level.
        """
        rows = list(
            Category.objects.filter(active=True)
            .values_list("id", "parent_id", "slug")
        )

        root_id = next((category_id for category_id, _, slug in rows if slug == value), None)
        if root_id is None:
            return queryset.none()

        category_ids = {root_id}
        changed = True
        while changed:
            changed = False
            for category_id, parent_id, _ in rows:
                if parent_id in category_ids and category_id not in category_ids:
                    category_ids.add(category_id)
                    changed = True

        return queryset.filter(category_id__in=category_ids)

    class Meta:
        model = Product
        fields = ("product_type", "featured", "new_arrival", "bestseller", "trending")
