from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.carts.models import Cart
from apps.carts.services import add_cart_item
from apps.common.tests.utils import delivery_location, simple_product
from apps.orders.models import Order
from apps.orders.services import checkout, transition_order
from apps.reviews.models import Review
from apps.reviews.services import create_review
from apps.shipping.models import ShippingMethod


class ReviewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone="01766666666", password="x", full_name="Customer"
        )
        self.product, _, _ = simple_product()
        cart = Cart.objects.create(user=self.user)
        add_cart_item(cart=cart, product=self.product, quantity=1)
        ship = ShippingMethod.objects.create(
            name="Standard", code="standard-review", base_charge=0
        )
        city, thana, _ = delivery_location()
        self.order = checkout(
            cart=cart,
            customer_data={
                "name": "Customer",
                "phone": self.user.phone,
                "district": city,
                "thana": thana,
                "address": "A",
                "label": "",
            },
            shipping_method=ship,
            payment_method="cod",
            request_user=self.user,
        )["order"]
        self.order_item = self.order.items.first()

    def deliver(self):
        for status in [
            Order.Status.CONFIRMED,
            Order.Status.PROCESSING,
            Order.Status.PACKED,
            Order.Status.SHIPPED,
            Order.Status.OUT_FOR_DELIVERY,
            Order.Status.DELIVERED,
        ]:
            self.order = transition_order(order=self.order, new_status=status)

    def test_review_rejected_before_delivery(self):
        with self.assertRaises(Exception):
            create_review(
                user=self.user,
                validated_data={
                    "product": self.product,
                    "order_item": self.order_item,
                    "rating": 5,
                    "comment": "Too early",
                },
            )

    def test_delivered_purchase_review_is_verified(self):
        self.deliver()
        review = create_review(
            user=self.user,
            validated_data={
                "product": self.product,
                "order_item": self.order_item,
                "rating": 5,
                "comment": "Delivered",
            },
        )
        self.assertTrue(review.verified_purchase)

    def test_mine_endpoint_returns_pending_own_reviews(self):
        self.deliver()
        review = create_review(
            user=self.user,
            validated_data={
                "product": self.product,
                "order_item": self.order_item,
                "rating": 5,
                "comment": "Delivered",
            },
        )
        self.assertEqual(review.status, Review.Status.PENDING)
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.get("/api/v1/reviews/mine/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["count"], 1)
        result = response.data["data"]["results"][0]
        self.assertEqual(result["id"], review.id)
        self.assertEqual(result["product_summary"]["id"], self.product.id)
        self.assertEqual(result["product_summary"]["slug"], self.product.slug)
        self.assertEqual(result["product_summary"]["name"], self.product.name)

    def test_eligible_endpoint_lists_only_unreviewed_delivered_items(self):
        self.deliver()
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.get("/api/v1/reviews/eligible/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["count"], 1)
        result = response.data["data"]["results"][0]
        self.assertEqual(result["id"], self.order_item.id)
        self.assertEqual(result["product_summary"]["id"], self.product.id)
        self.assertEqual(result["product_summary"]["slug"], self.product.slug)
