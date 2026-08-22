from decimal import Decimal

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.common.models import CheckoutSettings
from apps.common.tests.utils import delivery_location, simple_product
from apps.inventory.services import decrease_stock
from apps.shipping.models import ShippingMethod


class CheckoutTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.ship = ShippingMethod.objects.create(name="Standard", code="standard", base_charge=Decimal("0"), active=True)
        self.city, self.thana, _ = delivery_location()

    def payload(self, phone="01711111111"):
        return {
            "name": "Guest Customer",
            "phone": phone,
            "district": self.city.id,
            "thana": self.thana.id,
            "address": "House 10, Road 5",
            "shipping_method": self.ship.id,
            "payment_method": "cod",
            "coupon_code": "",
        }

    def cart_with(self, p):
        r = self.client.post("/api/v1/cart/items/", {"product": p.id, "quantity": 1}, format="json")
        token = r.data["data"]["cart_token"]
        self.client.credentials(HTTP_X_CART_TOKEN=token)
        return token

    def test_guest_checkout_creates_user_only_after_successful_order(self):
        p, _, _ = simple_product()
        self.cart_with(p)
        self.assertEqual(User.objects.count(), 0)
        r = self.client.post("/api/v1/checkout/", self.payload(), format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(User.objects.count(), 1)
        self.assertTrue(r.data["data"]["account_created"])
        self.assertFalse(r.data["data"]["existing_account"])
        self.assertIn("access", r.data["data"]["auth"])
        self.assertEqual(r.data["data"]["order"]["shipping_charge"], "60.00")

    def test_existing_phone_can_checkout_without_auto_authentication(self):
        existing = User.objects.create_user(phone="01722222222", password="Secret123!")
        p, _, _ = simple_product()
        self.cart_with(p)
        r = self.client.post("/api/v1/checkout/", self.payload("01722222222"), format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(User.objects.count(), 1)
        self.assertFalse(r.data["data"]["account_created"])
        self.assertTrue(r.data["data"]["existing_account"])
        self.assertNotIn("auth", r.data["data"])
        self.assertTrue(r.data["data"]["verification_required"])
        self.assertEqual(r.data["data"]["order"]["customer_phone"], existing.phone)

    @override_settings(DEBUG=True, ALLOW_INSECURE_EXISTING_CUSTOMER_AUTO_LOGIN=True)
    def test_existing_phone_auto_logs_in_when_verification_is_off_in_development(self):
        User.objects.create_user(phone="01744444444", password="Secret123!")
        CheckoutSettings.objects.create(existing_customer_otp_verification=False)
        p, _, _ = simple_product(sku="SIMPLE-BYPASS")
        self.cart_with(p)
        r = self.client.post("/api/v1/checkout/", self.payload("01744444444"), format="json")
        self.assertEqual(r.status_code, 201)
        self.assertFalse(r.data["data"]["verification_required"])
        self.assertTrue(r.data["data"]["verification_bypassed"])
        self.assertIn("access", r.data["data"]["auth"])

    @override_settings(DEBUG=False, ALLOW_INSECURE_EXISTING_CUSTOMER_AUTO_LOGIN=False)
    def test_verification_off_never_auto_logs_in_existing_phone_in_production(self):
        User.objects.create_user(phone="01766666666", password="Secret123!")
        CheckoutSettings.objects.create(existing_customer_otp_verification=False)
        p, _, _ = simple_product(sku="SIMPLE-PROD-GUARD")
        self.cart_with(p)
        r = self.client.post("/api/v1/checkout/", self.payload("01766666666"), format="json")
        self.assertEqual(r.status_code, 201)
        self.assertFalse(r.data["data"]["verification_required"])
        self.assertNotIn("auth", r.data["data"])

    def test_failed_stock_validation_does_not_create_user(self):
        p, si, wh = simple_product(stock=1)
        self.cart_with(p)
        decrease_stock(stock_item=si, warehouse=wh, quantity=1)
        r = self.client.post("/api/v1/checkout/", self.payload("01733333333"), format="json")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(User.objects.filter(phone="+8801733333333").exists())

    def test_thana_must_belong_to_selected_district(self):
        other_city, other_thana, _ = delivery_location(module_code="outside_dhaka", charge="120.00", city_name="Chittagong", thana_name="Panchlaish")
        p, _, _ = simple_product(sku="SIMPLE-MISMATCH")
        self.cart_with(p)
        payload = self.payload("01755555555")
        payload["district"] = self.city.id
        payload["thana"] = other_thana.id
        r = self.client.post("/api/v1/checkout/", payload, format="json")
        self.assertEqual(r.status_code, 400)
