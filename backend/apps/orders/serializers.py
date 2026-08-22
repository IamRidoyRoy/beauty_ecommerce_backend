from rest_framework import serializers

from apps.accounts.utils import PhoneFormatError, normalize_phone
from apps.delivery.models import City, Thana
from apps.payments.models import Payment
from apps.shipping.models import ShippingMethod

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

    def validate_phone(self, value):
        try:
            return normalize_phone(value)
        except PhoneFormatError as exc:
            raise serializers.ValidationError(str(exc))

    def validate(self, attrs):
        if attrs["thana"].city_id != attrs["district"].id:
            raise serializers.ValidationError({"thana": "Selected thana does not belong to the selected district."})
        return attrs


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

    class Meta:
        model = User
        fields = (
            "id", "uuid", "full_name", "phone", "email", "is_active", "created_at",
            "orders_count", "lifetime_spend", "average_order", "last_order",
        )


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
