from rest_framework import serializers

from apps.catalog.models import Product
from apps.orders.models import Order, OrderItem

from .models import Review, ReviewImage


REVIEWABLE_ORDER_STATUSES = {
    Order.Status.DELIVERED,
    Order.Status.RETURN_REQUESTED,
    Order.Status.PARTIALLY_RETURNED,
    Order.Status.RETURNED,
    Order.Status.REFUNDED,
}


class ReviewImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = ReviewImage
        fields = ("id", "image", "order")

    def get_image(self, obj):
        return obj.image.url if obj.image else None


class ReviewedProductSerializer(serializers.ModelSerializer):
    primary_image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ("id", "name", "slug", "sku", "product_type", "primary_image")

    def get_primary_image(self, obj):
        images = list(obj.images.all())
        image = next(
            (item for item in images if item.is_primary and item.variant_id is None),
            None,
        ) or next((item for item in images if item.variant_id is None), None)
        return image.image.url if image and image.image else None


class ReviewSerializer(serializers.ModelSerializer):
    images = ReviewImageSerializer(many=True, read_only=True)
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    product_summary = ReviewedProductSerializer(source="product", read_only=True)
    order_number = serializers.CharField(source="order_item.order.order_number", read_only=True)
    reviewed_sku = serializers.CharField(source="order_item.sku_snapshot", read_only=True)
    variant_snapshot = serializers.JSONField(source="order_item.variant_snapshot", read_only=True)

    class Meta:
        model = Review
        fields = (
            "id",
            "user",
            "user_name",
            "product",
            "product_summary",
            "order_item",
            "order_number",
            "reviewed_sku",
            "variant_snapshot",
            "rating",
            "title",
            "comment",
            "status",
            "verified_purchase",
            "images",
            "created_at",
        )
        read_only_fields = ("user", "status", "verified_purchase")

    def validate(self, attrs):
        request = self.context.get("request")
        order_item = attrs.get("order_item")
        product = attrs.get("product")

        if request and request.method == "POST":
            if not order_item:
                raise serializers.ValidationError(
                    {"order_item": "Choose a delivered purchased item to review."}
                )
            if not product:
                raise serializers.ValidationError({"product": "Product is required."})
            if order_item.product_id != product.id:
                raise serializers.ValidationError(
                    {"order_item": "Order item does not match this product."}
                )
            if not request.user.is_authenticated or order_item.order.user_id != request.user.id:
                raise serializers.ValidationError(
                    {"order_item": "This order item does not belong to your account."}
                )
            if order_item.order.order_status not in REVIEWABLE_ORDER_STATUSES:
                raise serializers.ValidationError(
                    {"order_item": "You can review this product after the order is delivered."}
                )
            if Review.objects.filter(user=request.user, order_item=order_item).exists():
                raise serializers.ValidationError(
                    {"order_item": "You have already reviewed this purchased item."}
                )

        return attrs


class EligibleReviewItemSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source="order.order_number", read_only=True)
    order_status = serializers.CharField(source="order.order_status", read_only=True)
    product_summary = ReviewedProductSerializer(source="product", read_only=True)

    class Meta:
        model = OrderItem
        fields = (
            "id",
            "product",
            "product_summary",
            "variant",
            "product_name_snapshot",
            "sku_snapshot",
            "variant_snapshot",
            "image_snapshot",
            "quantity",
            "order_number",
            "order_status",
        )


class AdminReviewSerializer(serializers.ModelSerializer):
    images = ReviewImageSerializer(many=True, read_only=True)
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    user_phone = serializers.CharField(source="user.phone", read_only=True)
    product_summary = ReviewedProductSerializer(source="product", read_only=True)
    order_number = serializers.CharField(source="order_item.order.order_number", read_only=True)
    reviewed_sku = serializers.CharField(source="order_item.sku_snapshot", read_only=True)
    variant_snapshot = serializers.JSONField(source="order_item.variant_snapshot", read_only=True)

    class Meta:
        model = Review
        fields = (
            "id",
            "user",
            "user_name",
            "user_phone",
            "product",
            "product_summary",
            "order_item",
            "order_number",
            "reviewed_sku",
            "variant_snapshot",
            "rating",
            "title",
            "comment",
            "status",
            "verified_purchase",
            "images",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("verified_purchase",)
