from rest_framework import serializers

from apps.accounts.utils import PhoneFormatError, normalize_phone
from apps.catalog.models import Product, ProductVariant
from apps.delivery.models import City, Thana
from apps.payments.models import Payment
from apps.shipping.models import ShippingMethod
from apps.inventory.models import StockItem
from apps.inventory.services import get_sellable_stock, resolve_stock_item

from .models import Order, OrderItem


class CheckoutSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=180)
    phone = serializers.CharField(max_length=24)
    district = serializers.PrimaryKeyRelatedField(queryset=City.objects.filter(active=True))
    thana = serializers.PrimaryKeyRelatedField(queryset=Thana.objects.filter(active=True))
    address = serializers.CharField()
    label = serializers.CharField(required=False, allow_blank=True)
    shipping_method = serializers.PrimaryKeyRelatedField(
        queryset=ShippingMethod.objects.filter(active=True),
        required=False,
        allow_null=True,
    )
    payment_method = serializers.ChoiceField(choices=Payment.Method.choices)
    coupon_code = serializers.CharField(required=False, allow_blank=True, max_length=60)
    order_note = serializers.CharField(required=False, allow_blank=True)
    # Browser attribution context used only for first-party server-side Meta CAPI.
    # These fields do not alter order pricing or fulfillment.
    event_source_url = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    fbp = serializers.CharField(required=False, allow_blank=True, max_length=255)
    fbc = serializers.CharField(required=False, allow_blank=True, max_length=255)
    marketing_consent = serializers.BooleanField(required=False, default=True)

    def validate_phone(self, value):
        try:
            return normalize_phone(value)
        except PhoneFormatError as exc:
            raise serializers.ValidationError(str(exc))

    def validate(self, attrs):
        if attrs["thana"].city_id != attrs["district"].id:
            raise serializers.ValidationError({"thana": "Selected thana does not belong to the selected district."})
        return attrs


class AdminOrderCreateItemSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.filter(status=Product.Status.ACTIVE))
    product_variant = serializers.PrimaryKeyRelatedField(
        queryset=ProductVariant.objects.filter(is_active=True, product__status=Product.Status.ACTIVE),
        required=False,
        allow_null=True,
    )
    quantity = serializers.IntegerField(min_value=1, max_value=999)

    def validate(self, attrs):
        product = attrs["product"]
        variant = attrs.get("product_variant")
        if product.product_type == Product.ProductType.SIMPLE:
            if variant is not None:
                raise serializers.ValidationError({"product_variant": "Simple products must not include a variant."})
        else:
            if variant is None:
                raise serializers.ValidationError({"product_variant": "Select a variant for this variable product."})
            if variant.product_id != product.id:
                raise serializers.ValidationError({"product_variant": "Selected variant does not belong to this product."})

        try:
            stock_item = resolve_stock_item(product=product if variant is None else None, variant=variant, create=False)
            available = int(get_sellable_stock(stock_item=stock_item))
        except StockItem.DoesNotExist:
            available = 0
        if attrs["quantity"] > available:
            raise serializers.ValidationError({"quantity": f"Only {available} unit(s) are currently available."})
        attrs["available_stock"] = available
        return attrs


class AdminOrderCreateSerializer(CheckoutSerializer):
    items = AdminOrderCreateItemSerializer(many=True, allow_empty=False)

    def validate_items(self, value):
        seen = set()
        for item in value:
            key = (item["product"].id, item.get("product_variant").id if item.get("product_variant") else None)
            if key in seen:
                raise serializers.ValidationError("Duplicate product/variant rows are not allowed. Increase the quantity instead.")
            seen.add(key)
        return value




class AdminOrderCouponPreviewSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=60)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=24)
    items = AdminOrderCreateItemSerializer(many=True, allow_empty=False)

    def validate_phone(self, value):
        if not value:
            return value
        try:
            return normalize_phone(value)
        except PhoneFormatError as exc:
            raise serializers.ValidationError(str(exc))

    def validate_items(self, value):
        seen = set()
        for item in value:
            key = (item["product"].id, item.get("product_variant").id if item.get("product_variant") else None)
            if key in seen:
                raise serializers.ValidationError("Duplicate product/variant rows are not allowed. Increase the quantity instead.")
            seen.add(key)
        return value

class PublicPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ("id", "method", "amount", "status", "paid_at")


class PublicOrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = (
            "id", "product", "variant", "product_name_snapshot", "sku_snapshot",
            "variant_snapshot", "image_snapshot", "quantity", "unit_price",
            "discount", "tax", "total", "returned_quantity",
        )


class AdminOrderItemSerializer(PublicOrderItemSerializer):
    class Meta(PublicOrderItemSerializer.Meta):
        fields = PublicOrderItemSerializer.Meta.fields + ("cost_price_snapshot",)


class OrderSerializer(serializers.ModelSerializer):
    items = PublicOrderItemSerializer(many=True, read_only=True)
    payments = PublicPaymentSerializer(many=True, read_only=True)
    shipping_method_name = serializers.CharField(source="shipping_method.name", read_only=True)

    class Meta:
        model = Order
        fields = (
            "id", "uuid", "order_number", "customer_name", "customer_phone",
            "shipping_address_snapshot", "shipping_method", "shipping_method_name",
            "coupon_code_snapshot", "promotion_snapshot", "subtotal", "discount",
            "shipping_charge", "tax", "total", "order_status", "payment_status",
            "fulfillment_status", "notes", "items", "payments", "created_at", "updated_at",
        )


class AdminOrderSerializer(serializers.ModelSerializer):
    items = AdminOrderItemSerializer(many=True, read_only=True)
    payments = PublicPaymentSerializer(many=True, read_only=True)
    shipping_method_name = serializers.CharField(source="shipping_method.name", read_only=True)

    class Meta:
        model = Order
        fields = (
            "id", "uuid", "order_number", "user", "customer_name", "customer_phone",
            "shipping_address_snapshot", "shipping_method", "shipping_method_name",
            "coupon_code_snapshot", "promotion_snapshot", "subtotal", "discount",
            "shipping_charge", "tax", "total", "order_status", "payment_status",
            "fulfillment_status", "notes", "items", "payments", "created_at", "updated_at",
        )


class OrderTransitionSerializer(serializers.Serializer):
    new_status = serializers.ChoiceField(choices=Order.Status.choices)

# Management customer serializers -------------------------------------------------
# Kept in the orders app because the commercial customer metrics are order-derived.
from apps.accounts.models import User
from apps.accounts.serializers import AddressSerializer


class AdminCustomerListSerializer(serializers.ModelSerializer):
    orders_count = serializers.IntegerField(read_only=True)
    lifetime_spend = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)
    average_order = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)
    last_order = serializers.DateTimeField(read_only=True, allow_null=True)
    checkout_address = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id", "uuid", "full_name", "phone", "email", "is_active", "created_at",
            "orders_count", "lifetime_spend", "average_order", "last_order", "checkout_address",
        )

    def get_checkout_address(self, obj):
        # Use the customer's saved default address when available; otherwise use
        # the most recently created saved address. The view prefetches addresses,
        # so this does not add per-customer database queries.
        addresses = list(obj.addresses.all())
        if not addresses:
            return None
        address = next((row for row in addresses if row.is_default), None) or max(addresses, key=lambda row: row.created_at)
        return {
            "id": address.id,
            "name": address.name,
            "phone": address.phone,
            "district": address.district,
            "thana": address.thana,
            "address": address.address,
            "label": address.label,
            "is_default": address.is_default,
        }


class AdminCustomerDetailSerializer(AdminCustomerListSerializer):
    addresses = AddressSerializer(many=True, read_only=True)
    orders = OrderSerializer(many=True, read_only=True)
    returns = serializers.SerializerMethodField()
    refunds = serializers.SerializerMethodField()
    reviews = serializers.SerializerMethodField()
    wishlist = serializers.SerializerMethodField()

    class Meta(AdminCustomerListSerializer.Meta):
        fields = AdminCustomerListSerializer.Meta.fields + (
            "gender", "date_of_birth", "email_verified", "phone_verified",
            "addresses", "orders", "returns", "refunds", "reviews", "wishlist",
        )

    def get_returns(self, obj):
        rows = getattr(obj, "return_requests", None)
        if rows is None:
            return []
        return [
            {
                "id": row.id,
                "order": row.order_id,
                "order_number": row.order.order_number if getattr(row, "order", None) else "",
                "reason": row.reason,
                "status": row.status,
                "created_at": row.created_at,
            }
            for row in rows.all()
        ]

    def get_refunds(self, obj):
        result = []
        for order in obj.orders.all():
            for row in order.refunds.all():
                result.append({
                    "id": row.id,
                    "order": order.id,
                    "order_number": order.order_number,
                    "amount": row.amount,
                    "reason": row.reason,
                    "status": row.status,
                    "created_at": row.created_at,
                })
        return result

    def get_reviews(self, obj):
        return [
            {
                "id": row.id,
                "product": row.product_id,
                "product_name": row.product.name if getattr(row, "product", None) else "",
                "rating": row.rating,
                "title": row.title,
                "comment": row.comment,
                "status": row.status,
                "verified_purchase": row.verified_purchase,
                "created_at": row.created_at,
            }
            for row in obj.reviews.all()
        ]

    def get_wishlist(self, obj):
        return [
            {
                "id": row.id,
                "product": row.product_id,
                "product_name": row.product.name if getattr(row, "product", None) else "",
            }
            for row in obj.wishlist_items.all()
        ]
