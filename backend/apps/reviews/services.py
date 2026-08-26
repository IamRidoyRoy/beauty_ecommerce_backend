from rest_framework.exceptions import ValidationError

from apps.orders.models import Order

from .models import Review


REVIEWABLE_ORDER_STATUSES = {
    Order.Status.DELIVERED,
    Order.Status.RETURN_REQUESTED,
    Order.Status.PARTIALLY_RETURNED,
    Order.Status.RETURNED,
    Order.Status.REFUNDED,
}


def create_review(*, user, validated_data):
    order_item = validated_data.get("order_item")
    product = validated_data.get("product")

    if order_item is None:
        raise ValidationError({"order_item": "A delivered purchased item is required."})
    if product is None or order_item.product_id != product.id:
        raise ValidationError({"order_item": "Order item does not match this product."})
    if order_item.order.user_id != user.id:
        raise ValidationError({"order_item": "This order item does not belong to your account."})
    if order_item.order.order_status not in REVIEWABLE_ORDER_STATUSES:
        raise ValidationError({"order_item": "You can review this product after the order is delivered."})
    if Review.objects.filter(user=user, order_item=order_item).exists():
        raise ValidationError({"order_item": "You have already reviewed this purchased item."})

    return Review.objects.create(
        user=user,
        verified_purchase=True,
        **validated_data,
    )
