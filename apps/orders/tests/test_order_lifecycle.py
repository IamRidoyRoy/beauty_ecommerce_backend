from decimal import Decimal
from django.test import TestCase
from apps.accounts.models import User
from apps.common.tests.utils import simple_product
from apps.carts.models import Cart
from apps.carts.services import add_cart_item
from apps.shipping.models import ShippingMethod
from apps.orders.services import checkout,transition_order
from apps.orders.models import Order
from apps.inventory.models import ProductStock
class OrderLifecycleTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user(phone="01744444444",password="x",full_name="Customer"); self.ship=ShippingMethod.objects.create(name="Ship",code="ship",base_charge=Decimal("60")); self.p,self.si,self.wh=simple_product(stock=5)
    def place(self):
        cart=Cart.objects.create(user=self.user); add_cart_item(cart=cart,product=self.p,quantity=2); return checkout(cart=cart,customer_data={"name":"Customer","phone":self.user.phone,"district":"Dhaka","thana":"Dhanmondi","address":"Test","label":"Home"},shipping_method=self.ship,payment_method="cod",request_user=self.user)["order"]
    def test_place_reserves_and_cancel_releases(self):
        order=self.place(); stock=ProductStock.objects.get(stock_item=self.si,warehouse=self.wh); self.assertEqual((stock.available_stock,stock.reserved_stock),(3,2)); order=transition_order(order=order,new_status=Order.Status.CANCELLED); stock.refresh_from_db(); self.assertEqual((stock.available_stock,stock.reserved_stock),(5,0))
    def test_deliver_consumes_reserved(self):
        order=self.place()
        for s in [Order.Status.CONFIRMED,Order.Status.PROCESSING,Order.Status.PACKED,Order.Status.READY_TO_SHIP,Order.Status.SHIPPED,Order.Status.OUT_FOR_DELIVERY,Order.Status.DELIVERED]: order=transition_order(order=order,new_status=s)
        stock=ProductStock.objects.get(stock_item=self.si,warehouse=self.wh); self.assertEqual((stock.available_stock,stock.reserved_stock),(3,0)); self.assertEqual(order.fulfillment_status,Order.FulfillmentStatus.FULFILLED)
    def test_invalid_transition_rejected(self):
        from rest_framework.exceptions import ValidationError
        order=self.place()
        with self.assertRaises(ValidationError): transition_order(order=order,new_status=Order.Status.DELIVERED)
