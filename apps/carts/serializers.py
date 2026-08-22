from rest_framework import serializers
from .models import Cart,CartItem
from apps.catalog.models import Product,ProductVariant
class CartItemSerializer(serializers.ModelSerializer):
    product=serializers.PrimaryKeyRelatedField(queryset=Product.objects.all(),required=False,allow_null=True)
    product_variant=serializers.PrimaryKeyRelatedField(queryset=ProductVariant.objects.select_related("product"),required=False,allow_null=True)
    unit_price=serializers.DecimalField(max_digits=12,decimal_places=2,read_only=True); line_total=serializers.DecimalField(max_digits=14,decimal_places=2,read_only=True)
    name=serializers.SerializerMethodField(); sku=serializers.SerializerMethodField(); variant=serializers.SerializerMethodField()
    class Meta: model=CartItem; fields=("id","product","product_variant","name","sku","variant","quantity","unit_price","line_total")
    def get_name(self,obj): return obj.product.name if obj.product_id else obj.product_variant.product.name
    def get_sku(self,obj): return obj.product.sku if obj.product_id else obj.product_variant.sku
    def get_variant(self,obj):
        if not obj.product_variant_id:return None
        return [{"attribute":v.attribute.name,"value":v.value} for v in obj.product_variant.attributes.all()]
    def validate(self,attrs):
        if self.instance: return attrs
        if bool(attrs.get("product"))==bool(attrs.get("product_variant")): raise serializers.ValidationError("Exactly one of product or product_variant is required.")
        return attrs
class CartSerializer(serializers.ModelSerializer):
    items=CartItemSerializer(many=True,read_only=True); subtotal=serializers.SerializerMethodField()
    class Meta: model=Cart; fields=("id","token","items","subtotal","updated_at")
    def get_subtotal(self,obj): return sum((x.line_total for x in obj.items.all()),0)
