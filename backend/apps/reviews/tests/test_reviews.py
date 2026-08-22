from decimal import Decimal
from django.test import TestCase
from apps.accounts.models import User
from apps.common.tests.utils import simple_product, delivery_location
from apps.carts.models import Cart
from apps.carts.services import add_cart_item
from apps.shipping.models import ShippingMethod
from apps.orders.services import checkout,transition_order
from apps.orders.models import Order
from apps.reviews.services import create_review
class ReviewTests(TestCase):
    def test_verified_purchase_is_server_derived(self):
        user=User.objects.create_user(phone="01766666666",password="x",full_name="Customer"); p,_,_=simple_product(); cart=Cart.objects.create(user=user); add_cart_item(cart=cart,product=p,quantity=1); ship=ShippingMethod.objects.create(name="S",code="s",base_charge=0); city,thana,_=delivery_location(); order=checkout(cart=cart,customer_data={"name":"Customer","phone":user.phone,"district":city,"thana":thana,"address":"A","label":""},shipping_method=ship,payment_method="cod",request_user=user)["order"]
        oi=order.items.first(); pre=create_review(user=user,validated_data={"product":p,"order_item":oi,"rating":5,"comment":"Before delivery"}); self.assertFalse(pre.verified_purchase); pre.delete()
        for s in [Order.Status.CONFIRMED,Order.Status.PROCESSING,Order.Status.PACKED,Order.Status.READY_TO_SHIP,Order.Status.SHIPPED,Order.Status.OUT_FOR_DELIVERY,Order.Status.DELIVERED]: order=transition_order(order=order,new_status=s)
        post=create_review(user=user,validated_data={"product":p,"order_item":oi,"rating":5,"comment":"Delivered"}); self.assertTrue(post.verified_purchase)
