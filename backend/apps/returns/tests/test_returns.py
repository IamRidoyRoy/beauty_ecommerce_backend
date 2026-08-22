from decimal import Decimal
from django.test import TestCase
from apps.accounts.models import User
from apps.common.tests.utils import simple_product, delivery_location
from apps.carts.models import Cart
from apps.carts.services import add_cart_item
from apps.shipping.models import ShippingMethod
from apps.orders.services import checkout,transition_order
from apps.orders.models import Order
from apps.returns.services import create_return_request,approve_return,receive_return
from apps.inventory.models import ProductStock
class ReturnTests(TestCase):
    def test_return_quantity_and_restock(self):
        user=User.objects.create_user(phone="01799999999",password="x",full_name="Customer"); p,si,wh=simple_product(stock=5); cart=Cart.objects.create(user=user); add_cart_item(cart=cart,product=p,quantity=2); ship=ShippingMethod.objects.create(name="S",code="ret-s",base_charge=0)
        city,thana,_=delivery_location(); order=checkout(cart=cart,customer_data={"name":"Customer","phone":user.phone,"district":city,"thana":thana,"address":"A","label":""},shipping_method=ship,payment_method="cod",request_user=user)["order"]
        for status in [Order.Status.CONFIRMED,Order.Status.PROCESSING,Order.Status.PACKED,Order.Status.READY_TO_SHIP,Order.Status.SHIPPED,Order.Status.OUT_FOR_DELIVERY,Order.Status.DELIVERED]: order=transition_order(order=order,new_status=status)
        before=ProductStock.objects.get(stock_item=si,warehouse=wh).available_stock; oi=order.items.first(); rr=create_return_request(order=order,user=user,items=[{"order_item":oi,"quantity":1,"restock":True}],reason="Return"); approve_return(return_request=rr); receive_return(return_request=rr,warehouse=wh); oi.refresh_from_db(); order.refresh_from_db(); stock=ProductStock.objects.get(stock_item=si,warehouse=wh)
        self.assertEqual(oi.returned_quantity,1); self.assertEqual(stock.available_stock,before+1); self.assertEqual(order.order_status,Order.Status.PARTIALLY_RETURNED)
