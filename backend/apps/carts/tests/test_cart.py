from django.test import TestCase
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.common.tests.utils import simple_product,variable_product
class AnonymousCartTests(TestCase):
    def setUp(self): self.client=APIClient()
    def test_browsing_and_cart_do_not_create_user(self):
        p,_,_=simple_product(); self.client.get("/api/v1/products/"); self.assertEqual(User.objects.count(),0)
        r=self.client.post("/api/v1/cart/items/",{"product":p.id,"quantity":1},format="json"); self.assertEqual(r.status_code,201); self.assertEqual(User.objects.count(),0); self.assertTrue(r.data["data"]["cart_token"])
    def test_anonymous_simple_product(self):
        p,_,_=simple_product(); r=self.client.post("/api/v1/cart/items/",{"product":p.id,"quantity":2},format="json"); self.assertEqual(r.status_code,201); self.assertIsNone(r.data["data"]["item"]["product_variant"])
    def test_anonymous_variant_product(self):
        p,v,_,_=variable_product(); r=self.client.post("/api/v1/cart/items/",{"product_variant":v.id,"quantity":1},format="json"); self.assertEqual(r.status_code,201); self.assertEqual(r.data["data"]["item"]["product_variant"],v.id)
    def test_variable_missing_variant_rejected(self):
        p,v,_,_=variable_product(); r=self.client.post("/api/v1/cart/items/",{"product":p.id,"quantity":1},format="json"); self.assertEqual(r.status_code,400)
    def test_stock_limit(self):
        p,_,_=simple_product(stock=2); r=self.client.post("/api/v1/cart/items/",{"product":p.id,"quantity":3},format="json"); self.assertEqual(r.status_code,400)
