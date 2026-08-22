from rest_framework import serializers
from .models import *
from .services import resolve_stock_item

class WarehouseSerializer(serializers.ModelSerializer):
    class Meta: model=Warehouse; fields="__all__"
class SupplierSerializer(serializers.ModelSerializer):
    class Meta: model=Supplier; fields="__all__"
class StockItemSerializer(serializers.ModelSerializer):
    sku=serializers.SerializerMethodField(); name=serializers.SerializerMethodField()
    class Meta: model=StockItem; fields=("id","product","variant","sku","name")
    def get_sku(self,obj): return obj.product.sku if obj.product_id else obj.variant.sku
    def get_name(self,obj): return obj.product.name if obj.product_id else obj.variant.product.name
class ProductStockSerializer(serializers.ModelSerializer):
    stock_item_detail=StockItemSerializer(source="stock_item",read_only=True); warehouse_name=serializers.CharField(source="warehouse.name",read_only=True)
    class Meta: model=ProductStock; fields=("id","stock_item","stock_item_detail","warehouse","warehouse_name","available_stock","reserved_stock","damaged_stock","incoming_stock","reorder_level","low_stock_threshold","updated_at")
class StockMovementSerializer(serializers.ModelSerializer):
    class Meta: model=StockMovement; fields="__all__"; read_only_fields=("created_by",)
class PurchaseItemSerializer(serializers.ModelSerializer):
    remaining_quantity=serializers.SerializerMethodField()
    class Meta: model=PurchaseItem; fields=("id","purchase","product","product_variant","quantity","received_quantity","remaining_quantity","unit_cost","discount","tax","total"); read_only_fields=("received_quantity",)
    def get_remaining_quantity(self,obj): return obj.quantity-obj.received_quantity
    def validate(self,attrs):
        product=attrs.get("product",getattr(self.instance,"product",None)); variant=attrs.get("product_variant",getattr(self.instance,"product_variant",None))
        if bool(product)==bool(variant): raise serializers.ValidationError("Exactly one of product or product_variant is required.")
        if product and product.product_type!="simple": raise serializers.ValidationError({"product":"Variable products require product_variant."})
        if variant and variant.product.product_type!="variable": raise serializers.ValidationError({"product_variant":"Invalid variant target."})
        return attrs
class PurchaseSerializer(serializers.ModelSerializer):
    items=PurchaseItemSerializer(many=True,read_only=True)
    class Meta: model=Purchase; fields="__all__"; read_only_fields=("status","created_by","approved_by","received_by","received_at")
class ReceivePurchaseSerializer(serializers.Serializer):
    receipts=serializers.ListField(child=serializers.DictField(),allow_empty=False)
    def validate_receipts(self,rows):
        for row in rows:
            if "item_id" not in row or "quantity" not in row: raise serializers.ValidationError("Each receipt needs item_id and quantity.")
        return rows
class TransferSerializer(serializers.Serializer):
    stock_item=serializers.PrimaryKeyRelatedField(queryset=StockItem.objects.all())
    source_warehouse=serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.filter(is_active=True))
    destination_warehouse=serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.filter(is_active=True))
    quantity=serializers.IntegerField(min_value=1); note=serializers.CharField(required=False,allow_blank=True)
class AdjustStockSerializer(serializers.Serializer):
    stock_item=serializers.PrimaryKeyRelatedField(queryset=StockItem.objects.all()); warehouse=serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.filter(is_active=True)); new_quantity=serializers.IntegerField(min_value=0); note=serializers.CharField()
