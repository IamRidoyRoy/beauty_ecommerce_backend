from django.core.exceptions import ValidationError
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.common.tests.utils import base_catalog,simple_product,variable_product
from apps.catalog.models import Product,ProductImage,ProductVariant
from apps.catalog.services import publish_product
class ProductArchitectureTests(TestCase):
    def test_simple_product_has_no_fake_variant(self):
        p,_,_=simple_product(); self.assertEqual(p.product_type,"simple"); self.assertFalse(p.variants.exists()); self.assertTrue(p.sku)
    def test_simple_requires_sku(self):
        brand,cat,_=base_catalog(); p=Product(name="Bad",slug="bad",product_type="simple",brand=brand,category=cat,base_price=1)
        with self.assertRaises(ValidationError): p.full_clean()
    def test_variable_requires_active_variant_before_publish(self):
        brand,cat,_=base_catalog(); p=Product.objects.create(name="Draft Variable",slug="draft-variable",product_type="variable",brand=brand,category=cat,base_price=100)
        from rest_framework.exceptions import ValidationError as DRFValidationError
        with self.assertRaises(DRFValidationError): publish_product(product=p)
        ProductVariant.objects.create(product=p,sku="ACTIVE-VAR",is_active=True); publish_product(product=p); p.refresh_from_db(); self.assertEqual(p.status,"active")
    def test_product_and_variant_images(self):
        p,v,_,_=variable_product(); gif=b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        a=ProductImage.objects.create(product=p,image=SimpleUploadedFile("p.gif",gif,content_type="image/gif"),is_primary=True); b=ProductImage.objects.create(product=p,variant=v,image=SimpleUploadedFile("v.gif",gif,content_type="image/gif"),is_primary=True)
        self.assertIsNone(a.variant_id); self.assertEqual(b.variant_id,v.id)
