from apps.orders.models import Order

def create_review(*,user,validated_data):
    oi=validated_data.get("order_item"); verified=bool(oi and oi.order.user_id==user.id and oi.order.order_status in {Order.Status.DELIVERED,Order.Status.RETURN_REQUESTED,Order.Status.PARTIALLY_RETURNED,Order.Status.RETURNED,Order.Status.REFUNDED})
    from .models import Review
    return Review.objects.create(user=user,verified_purchase=verified,**validated_data)
