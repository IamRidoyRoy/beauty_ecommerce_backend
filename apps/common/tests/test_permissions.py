from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from apps.accounts.models import User,UserRole
class PermissionTests(TestCase):
    def auth(self,user):
        c=APIClient(); c.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}"); return c
    def test_customer_cannot_access_admin_products(self):
        u=User.objects.create_user(phone="01777777777",password="x"); r=self.auth(u).get("/api/v1/admin/products/"); self.assertEqual(r.status_code,403)
    def test_product_manager_can_access_admin_products(self):
        u=User.objects.create_user(phone="01788888888",password="x",role=UserRole.PRODUCT_MANAGER,is_staff=True); r=self.auth(u).get("/api/v1/admin/products/"); self.assertEqual(r.status_code,200)
