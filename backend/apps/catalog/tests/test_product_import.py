from io import BytesIO
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APITestCase
from apps.accounts.models import User,UserRole
from apps.catalog.models import Brand,Category,Product

class ProductImportTests(APITestCase):
    def setUp(self):
        self.user=User.objects.create_user(phone="01700000001",password="pass12345",role=UserRole.PRODUCT_MANAGER,is_staff=True)
        self.client.force_authenticate(self.user)
        Brand.objects.create(name="CeraVe",slug="cerave")
        Category.objects.create(name="Skincare",slug="skincare")
    def test_csv_import_simple_product(self):
        content=b"name,product_type,sku,brand,category,base_price,status\nCleanser,simple,SKU-1,CeraVe,Skincare,1000,draft\n"
        upload=SimpleUploadedFile("products.csv",content,content_type="text/csv")
        response=self.client.post("/api/v1/admin/products/import-file/",{"file":upload},format="multipart")
        self.assertEqual(response.status_code,200,response.data)
        self.assertTrue(Product.objects.filter(sku="SKU-1").exists())
