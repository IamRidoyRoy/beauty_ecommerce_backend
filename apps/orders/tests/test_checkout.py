from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.common.tests.utils import simple_product,variable_product
from apps.shipping.models import ShippingMethod
from apps.inventory.services import decrease_stock
class CheckoutTests(TestCase):
    def setUp(self):
        self.client=APIClient(); self.ship=ShippingMethod.objects.create(name="Inside Dhaka",code="dhaka",base_charge=Decimal("60"),active=True)
    def payload(self,phone="01711111111"):
        return {"name":"Guest Customer","phone":phone,"district":"Dhaka","thana":"Dhanmondi","address":"House 10, Road 5","shipping_method":self.ship.id,"payment_method":"cod","coupon_code":""}
    def cart_with(self,p):
        r=self.client.post("/api/v1/cart/items/",{"product":p.id,"quantity":1},format="json"); token=r.data["data"]["cart_token"]; self.client.credentials(HTTP_X_CART_TOKEN=token); return token
    def test_guest_checkout_creates_user_only_after_successful_order(self):
        p,_,_=simple_product(); self.cart_with(p); self.assertEqual(User.objects.count(),0)
        r=self.client.post("/api/v1/checkout/",self.payload(),format="json"); self.assertEqual(r.status_code,201); self.assertEqual(User.objects.count(),1); self.assertTrue(r.data["data"]["account_created"]); self.assertIn("access",r.data["data"]["auth"])
    def test_existing_phone_never_auto_authenticates_anonymous(self):
        User.objects.create_user(phone="01722222222",password="Secret123!"); p,_,_=simple_product(); self.cart_with(p)
        r=self.client.post("/api/v1/checkout/",self.payload("01722222222"),format="json"); self.assertEqual(r.status_code,409); self.assertEqual(r.data.get("code"),"ACCOUNT_EXISTS_VERIFICATION_REQUIRED"); self.assertNotIn("auth",r.data.get("data",{}))
    def test_failed_stock_validation_does_not_create_user(self):
        p,si,wh=simple_product(stock=1); self.cart_with(p); decrease_stock(stock_item=si,warehouse=wh,quantity=1)
        r=self.client.post("/api/v1/checkout/",self.payload("01733333333"),format="json"); self.assertEqual(r.status_code,400); self.assertFalse(User.objects.filter(phone="01733333333").exists())
