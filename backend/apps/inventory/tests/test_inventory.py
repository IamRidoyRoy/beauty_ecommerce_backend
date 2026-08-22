from decimal import Decimal
from datetime import date
from django.test import TestCase
from rest_framework.exceptions import ValidationError
from apps.accounts.models import User
from apps.common.tests.utils import simple_product,variable_product,base_catalog
from apps.inventory.models import Supplier,Purchase,PurchaseItem,ProductStock
from apps.inventory.services import increase_stock,get_sellable_stock,receive_purchase,transfer_stock
class InventoryTests(TestCase):
    def test_simple_and_variant_stock_are_distinct_native_targets(self):
        p,si,wh=simple_product(stock=3); vp,v,vsi,_=variable_product(stock=4); self.assertEqual(si.product_id,p.id); self.assertIsNone(si.variant_id); self.assertEqual(vsi.variant_id,v.id); self.assertIsNone(vsi.product_id); self.assertEqual(get_sellable_stock(stock_item=si),3); self.assertEqual(get_sellable_stock(stock_item=vsi),4)
    def test_partial_full_receive_and_prevent_double_receive(self):
        p,si,wh=simple_product(stock=0); supplier=Supplier.objects.create(name="Supplier"); admin=User.objects.create_superuser(phone="01911111111",password="x")
        po=Purchase.objects.create(purchase_number="PO-1",supplier=supplier,warehouse=wh,purchase_date=date.today(),status=Purchase.Status.APPROVED,created_by=admin)
        item=PurchaseItem.objects.create(purchase=po,product=p,quantity=10,unit_cost=Decimal("50"),total=Decimal("500"))
        receive_purchase(purchase=po,receipts=[{"item_id":item.id,"quantity":4}],user=admin); item.refresh_from_db(); po.refresh_from_db(); self.assertEqual(item.received_quantity,4); self.assertEqual(po.status,Purchase.Status.PARTIAL); self.assertEqual(get_sellable_stock(stock_item=si),4)
        receive_purchase(purchase=po,receipts=[{"item_id":item.id,"quantity":6}],user=admin); item.refresh_from_db(); self.assertEqual(item.received_quantity,10); self.assertEqual(get_sellable_stock(stock_item=si),10)
        with self.assertRaises(ValidationError): receive_purchase(purchase=po,receipts=[{"item_id":item.id,"quantity":1}],user=admin)
        self.assertEqual(get_sellable_stock(stock_item=si),10)
    def test_transfer(self):
        p,si,source=simple_product(stock=10); from apps.inventory.models import Warehouse
        dest=Warehouse.objects.create(name="Hub",code="HUB"); transfer_stock(stock_item=si,source_warehouse=source,destination_warehouse=dest,quantity=3); self.assertEqual(ProductStock.objects.get(stock_item=si,warehouse=source).available_stock,7); self.assertEqual(ProductStock.objects.get(stock_item=si,warehouse=dest).available_stock,3)
