from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.common.tests.utils import delivery_location, simple_product, variable_product
from apps.orders.models import Order
from apps.promotions.models import Coupon
from apps.shipping.models import ShippingMethod


class AdminOrderCreateTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(
            phone="01710000000", password="Secret123!", full_name="Order Manager",
            role=UserRole.ORDER_MANAGER, is_staff=True,
        )
        self.client.force_authenticate(self.staff)
        self.city, self.thana, _ = delivery_location()
        self.ship = ShippingMethod.objects.create(
            name="Standard", code="admin-standard", base_charge=Decimal("0"), active=True
        )

    def base_payload(self):
        return {
            "name": "Counter Customer",
            "phone": "01722223333",
            "district": self.city.id,
            "thana": self.thana.id,
            "address": "House 10, Road 5",
            "shipping_method": self.ship.id,
            "payment_method": "cod",
            "coupon_code": "",
            "order_note": "Created from dashboard",
        }

    def test_order_manager_can_create_simple_product_order(self):
        product, _, _ = simple_product(sku="ADMIN-SIMPLE", stock=5)
        payload = {**self.base_payload(), "items": [{"product": product.id, "quantity": 2}]}
        response = self.client.post("/api/v1/admin/orders/create-order/", payload, format="json")
        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(order_number=response.data["data"]["order"]["order_number"])
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().quantity, 2)
        self.assertEqual(order.notes, "Created from dashboard")

    def test_order_manager_can_create_variable_product_order(self):
        product, variant, _, _ = variable_product(sku="ADMIN-VAR", stock=5)
        payload = {**self.base_payload(), "items": [{"product": product.id, "product_variant": variant.id, "quantity": 1}]}
        response = self.client.post("/api/v1/admin/orders/create-order/", payload, format="json")
        self.assertEqual(response.status_code, 201)
        item = Order.objects.get(order_number=response.data["data"]["order"]["order_number"]).items.get()
        self.assertEqual(item.variant_id, variant.id)
        self.assertEqual(item.sku_snapshot, variant.sku)

    def test_variable_product_requires_variant(self):
        product, _, _, _ = variable_product(sku="ADMIN-MISSING-VAR", stock=5)
        payload = {**self.base_payload(), "items": [{"product": product.id, "quantity": 1}]}
        response = self.client.post("/api/v1/admin/orders/create-order/", payload, format="json")
        self.assertEqual(response.status_code, 400)

    def test_admin_order_rejects_quantity_above_sellable_stock(self):
        product, _, _ = simple_product(sku="ADMIN-STOCK-LIMIT", stock=2)
        payload = {**self.base_payload(), "items": [{"product": product.id, "quantity": 3}]}
        response = self.client.post("/api/v1/admin/orders/create-order/", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("items", response.data["errors"])

    def test_admin_order_creates_new_customer_for_new_phone(self):
        product, _, _ = simple_product(sku="ADMIN-NEW-CUSTOMER", stock=2)
        payload = {**self.base_payload(), "phone": "01733334444", "name": "New Dashboard Customer", "items": [{"product": product.id, "quantity": 1}]}
        response = self.client.post("/api/v1/admin/orders/create-order/", payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["data"]["account_created"])
        self.assertTrue(User.objects.filter(phone="+8801733334444", role=UserRole.CUSTOMER).exists())


    def test_admin_can_preview_coupon_discount_before_order_creation(self):
        product, _, _ = simple_product(sku="ADMIN-COUPON-PREVIEW", stock=5)
        Coupon.objects.create(
            code="SAVE10", coupon_type=Coupon.Type.PERCENTAGE, value=Decimal("10"), active=True
        )
        payload = {
            "code": "SAVE10",
            "phone": "01722223333",
            "items": [{"product": product.id, "quantity": 2}],
        }
        response = self.client.post("/api/v1/admin/orders/validate-coupon/", payload, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["code"], "SAVE10")
        self.assertGreater(Decimal(response.data["data"]["coupon_discount"]), Decimal("0"))

    def test_created_order_snapshots_coupon_discount_for_invoice(self):
        product, _, _ = simple_product(sku="ADMIN-COUPON-ORDER", stock=5)
        Coupon.objects.create(
            code="LESS50", coupon_type=Coupon.Type.FIXED, value=Decimal("50"), active=True
        )
        payload = {**self.base_payload(), "coupon_code": "LESS50", "items": [{"product": product.id, "quantity": 1}]}
        response = self.client.post("/api/v1/admin/orders/create-order/", payload, format="json")
        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(order_number=response.data["data"]["order"]["order_number"])
        self.assertEqual(order.coupon_code_snapshot, "LESS50")
        coupon_rows = [row for row in order.promotion_snapshot if row.get("type") == "coupon"]
        self.assertEqual(len(coupon_rows), 1)
        self.assertEqual(Decimal(coupon_rows[0]["discount"]), Decimal("50"))
