from rest_framework import serializers

from apps.catalog.models import Product, ProductVariant

from .models import Cart, CartItem


class CartItemSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        required=False,
        allow_null=True,
    )
    product_variant = serializers.PrimaryKeyRelatedField(
        queryset=ProductVariant.objects.select_related("product"),
        required=False,
        allow_null=True,
    )
    unit_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    line_total = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )
    name = serializers.SerializerMethodField()
    sku = serializers.SerializerMethodField()
    variant = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = (
            "id",
            "product",
            "product_variant",
            "name",
            "sku",
            "variant",
            "quantity",
            "unit_price",
            "line_total",
        )

    def get_name(self, obj):
        return obj.product.name if obj.product_id else obj.product_variant.product.name

    def get_sku(self, obj):
        return obj.product.sku if obj.product_id else obj.product_variant.sku

    def get_variant(self, obj):
        if not obj.product_variant_id:
            return None
        return [
            {"attribute": value.attribute.name, "value": value.value}
            for value in obj.product_variant.attributes.all()
        ]

    def validate(self, attrs):
        """
        Public cart payloads intentionally support:

        Simple product:
            {"product": 10, "quantity": 1}

        Variable product:
            {"product": 20, "product_variant": 105, "quantity": 1}

        CartItem itself still keeps the database XOR invariant.  For a
        variable product we validate that the variant belongs to the supplied
        product, then normalize the inventory target to product_variant only.
        """
        if self.instance:
            return attrs

        product = attrs.get("product")
        product_variant = attrs.get("product_variant")

        if product is None and product_variant is None:
            raise serializers.ValidationError(
                {"product": "Product or product_variant is required."}
            )

        if product_variant is not None:
            if product is not None and product_variant.product_id != product.id:
                raise serializers.ValidationError(
                    {
                        "product_variant": (
                            "Selected variant does not belong to the supplied product."
                        )
                    }
                )

            # Database/storage invariant: a variable CartItem owns the variant
            # target only.  The base product remains available through
            # product_variant.product.
            attrs["product"] = None

        return attrs


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ("id", "token", "items", "subtotal", "updated_at")

    def get_subtotal(self, obj):
        return sum((item.line_total for item in obj.items.all()), 0)
