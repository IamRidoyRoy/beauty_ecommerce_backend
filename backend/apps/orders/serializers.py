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
