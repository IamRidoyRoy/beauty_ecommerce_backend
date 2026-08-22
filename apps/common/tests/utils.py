from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.catalog.models import Brand,Category,Product,ProductVariant,Attribute,AttributeValue,VariantAttributeValue
from apps.inventory.models import Warehouse
from apps.inventory.services import resolve_stock_item,increase_stock

def base_catalog():
    brand,_=Brand.objects.get_or_create(name="Test Brand",slug="test-brand")
    cat,_=Category.objects.get_or_create(name="Skincare",slug="skincare")
    wh,_=Warehouse.objects.get_or_create(name="Main",code="MAIN")
    return brand,cat,wh

def simple_product(sku="SIMPLE-1",stock=10):
    brand,cat,wh=base_catalog(); p=Product.objects.create(name=f"Simple {sku}",slug=sku.lower(),product_type=Product.ProductType.SIMPLE,sku=sku,brand=brand,category=cat,base_price=Decimal("100.00"),cost_price=Decimal("60.00"),status=Product.Status.ACTIVE)
    si=resolve_stock_item(product=p); increase_stock(stock_item=si,warehouse=wh,quantity=stock); return p,si,wh

def variable_product(sku="VAR-1",stock=10):
    brand,cat,wh=base_catalog(); p=Product.objects.create(name=f"Variable {sku}",slug=f"product-{sku.lower()}",product_type=Product.ProductType.VARIABLE,brand=brand,category=cat,base_price=Decimal("120.00"),status=Product.Status.ACTIVE)
    attr,_=Attribute.objects.get_or_create(name="Shade",slug="shade"); val,_=AttributeValue.objects.get_or_create(attribute=attr,slug=f"shade-{sku.lower()}",defaults={"value":"Beige"})
    v=ProductVariant.objects.create(product=p,sku=sku,price_override=Decimal("130.00"),cost_price=Decimal("70.00")); VariantAttributeValue.objects.create(variant=v,attribute_value=val)
    si=resolve_stock_item(variant=v); increase_stock(stock_item=si,warehouse=wh,quantity=stock); return p,v,si,wh
