from decimal import Decimal
from django.test import TestCase
from rest_framework.exceptions import ValidationError
from apps.accounts.models import User
from apps.common.tests.utils import simple_product, delivery_location
from apps.carts.models import Cart
from apps.carts.services import add_cart_item
from apps.shipping.models import ShippingMethod
from apps.orders.services import checkout,transition_order
from apps.orders.models import Order
from apps.payments.services import mark_payment_paid
from apps.returns.services import create_refund,complete_refund
from apps.payments.models import Payment
class RefundTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user(phone="01755555555",password="x",full_name="Customer"); p,_,_=simple_product(); cart=Cart.objects.create(user=self.user); add_cart_item(cart=cart,product=p,quantity=1); ship=ShippingMethod.objects.create(name="S",code="s",base_charge=0)
        city,thana,_=delivery_location(); self.order=checkout(cart=cart,customer_data={"name":"Customer","phone":self.user.phone,"district":city,"thana":thana,"address":"A","label":""},shipping_method=ship,payment_method="card",request_user=self.user)["order"]
        self.payment=mark_payment_paid(payment=self.order.payments.first(),transaction_id="TX")
    def test_refund_limit(self):
        r=create_refund(payment=self.payment,amount=Decimal("60"));
        with self.assertRaises(ValidationError): create_refund(payment=self.payment,amount=self.payment.amount)
        complete_refund(refund=r); self.payment.refresh_from_db(); self.assertEqual(self.payment.status,Payment.Status.PARTIAL_REFUND)
