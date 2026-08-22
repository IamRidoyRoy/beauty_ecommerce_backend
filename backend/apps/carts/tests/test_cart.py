from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.common.tests.utils import simple_product, variable_product


class AnonymousCartTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_browsing_and_cart_do_not_create_user(self):
        product, _, _ = simple_product()
        self.client.get("/api/v1/products/")
        self.assertEqual(User.objects.count(), 0)

        response = self.client.post(
            "/api/v1/cart/items/",
            {"product": product.id, "quantity": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(User.objects.count(), 0)
        self.assertTrue(response.data["data"]["cart_token"])

    def test_anonymous_simple_product(self):
        product, _, _ = simple_product()
        response = self.client.post(
            "/api/v1/cart/items/",
            {"product": product.id, "quantity": 2},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["data"]["item"]["product"], product.id)
        self.assertIsNone(response.data["data"]["item"]["product_variant"])

    def test_anonymous_variant_product_accepts_product_and_variant(self):
        product, variant, _, _ = variable_product()
        response = self.client.post(
            "/api/v1/cart/items/",
            {
                "product": product.id,
                "product_variant": variant.id,
                "quantity": 1,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.data["data"]["item"]["product"])
        self.assertEqual(
            response.data["data"]["item"]["product_variant"],
            variant.id,
        )

    def test_anonymous_variant_product_also_accepts_variant_only(self):
        _, variant, _, _ = variable_product()
        response = self.client.post(
            "/api/v1/cart/items/",
            {"product_variant": variant.id, "quantity": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.data["data"]["item"]["product_variant"],
            variant.id,
        )

    def test_mismatched_product_and_variant_rejected(self):
        variable, variant, _, _ = variable_product()
        other_product, _, _ = simple_product()
        self.assertNotEqual(variable.id, other_product.id)

        response = self.client.post(
            "/api/v1/cart/items/",
            {
                "product": other_product.id,
                "product_variant": variant.id,
                "quantity": 1,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("product_variant", response.data["errors"])

    def test_variable_missing_variant_rejected(self):
        product, _, _, _ = variable_product()
        response = self.client.post(
            "/api/v1/cart/items/",
            {"product": product.id, "quantity": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_stock_limit(self):
        product, _, _ = simple_product(stock=2)
        response = self.client.post(
            "/api/v1/cart/items/",
            {"product": product.id, "quantity": 3},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
