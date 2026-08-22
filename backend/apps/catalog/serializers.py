from rest_framework import serializers
from .models import *

class CategorySerializer(serializers.ModelSerializer):
    class Meta: model=Category; fields=("id","name","slug","parent","image","description","active","order","seo")
    def validate_parent(self,parent):
        if not self.instance or not parent:return parent
        if parent.pk==self.instance.pk: raise serializers.ValidationError("Category cannot be its own parent.")
        cursor=parent
        while cursor:
            if cursor.pk==self.instance.pk: raise serializers.ValidationError("Category hierarchy cannot contain a cycle.")
            cursor=cursor.parent
        return parent
class BrandSerializer(serializers.ModelSerializer):
    class Meta: model=Brand; fields=("id","name","slug","logo","cover","description","country","website","featured","active","seo")
class AttributeValueSerializer(serializers.ModelSerializer):
    attribute=serializers.CharField(source="attribute.name",read_only=True)
    class Meta: model=AttributeValue; fields=("id","attribute","value","slug","swatch","metadata")
class VariantSerializer(serializers.ModelSerializer):
    attributes=AttributeValueSerializer(many=True,read_only=True)
    selling_price=serializers.DecimalField(max_digits=12,decimal_places=2,read_only=True)
    available_stock=serializers.IntegerField(read_only=True,default=0)
    class Meta: model=ProductVariant; fields=("id","uuid","product","sku","barcode","price_override","selling_price","weight","is_active","available_stock","attributes")
class ProductImageSerializer(serializers.ModelSerializer):
    class Meta: model=ProductImage; fields=("id","product","variant","image","image_type","alt_text","order","is_primary")

    def to_representation(self, instance):
        # Keep media URLs host-agnostic. The storefront/dashboard can then resolve
        # /media/... against the configured Django origin on localhost, LAN or CDN.
        data = super().to_representation(instance)
        data["image"] = instance.image.url if instance.image else None
        return data

    def validate(self, attrs):
        product=attrs.get("product") or getattr(self.instance,"product",None); variant=attrs.get("variant") or getattr(self.instance,"variant",None)
        if variant and product and variant.product_id!=product.id: raise serializers.ValidationError({"variant":"Variant must belong to product."})
        return attrs
    def create(self,validated_data):
        scope=ProductImage.objects.filter(product=validated_data["product"],variant=validated_data.get("variant"))
        if validated_data.get("is_primary"):
            scope.filter(is_primary=True).update(is_primary=False)
        elif not scope.filter(is_primary=True).exists():
            validated_data["is_primary"]=True
        return super().create(validated_data)
    def update(self,instance,validated_data):
        if validated_data.get("is_primary"):
            ProductImage.objects.filter(product=validated_data.get("product",instance.product),variant=validated_data.get("variant",instance.variant),is_primary=True).exclude(pk=instance.pk).update(is_primary=False)
        return super().update(instance,validated_data)
class BeautyProfileSerializer(serializers.ModelSerializer):
    skin_types=serializers.SlugRelatedField(many=True,read_only=True,slug_field="name")
    hair_types=serializers.SlugRelatedField(many=True,read_only=True,slug_field="name")
    concerns=serializers.SlugRelatedField(many=True,read_only=True,slug_field="name")
    ingredients=serializers.SlugRelatedField(many=True,read_only=True,slug_field="name")
    class Meta: model=ProductBeautyProfile; fields=("benefits","ingredients_text","how_to_use","precautions","country_of_origin","shelf_life","pao","skin_types","hair_types","concerns","ingredients")
class ProductClaimSerializer(serializers.ModelSerializer):
    name=serializers.CharField(source="claim.name",read_only=True)
    class Meta: model=ProductClaim; fields=("id","name","is_verified","source_url")
class ProductListSerializer(serializers.ModelSerializer):
    brand=BrandSerializer(read_only=True); category=CategorySerializer(read_only=True)
    primary_image=serializers.SerializerMethodField(); price=serializers.SerializerMethodField(); available_stock=serializers.SerializerMethodField(); in_stock=serializers.SerializerMethodField()
    class Meta: model=Product; fields=("id","uuid","name","slug","product_type","sku","brand","category","base_price","compare_at_price","status","featured","new_arrival","bestseller","trending","primary_image","price","available_stock","in_stock")
    def get_primary_image(self,obj):
        image=next((x for x in obj.images.all() if x.is_primary and x.variant_id is None),None) or next(iter(obj.images.all()),None)
        return ProductImageSerializer(image,context=self.context).data if image else None
    def get_price(self,obj):
        if obj.product_type==Product.ProductType.SIMPLE: return {"min":str(obj.base_price),"max":str(obj.base_price)}
        prices=[v.selling_price for v in obj.variants.all() if v.is_active]
        return {"min":str(min(prices)) if prices else None,"max":str(max(prices)) if prices else None}
    def get_available_stock(self,obj):
        return getattr(obj,"simple_available_stock",0) if obj.product_type==Product.ProductType.SIMPLE else getattr(obj,"variant_available_stock",0)
    def get_in_stock(self,obj): return self.get_available_stock(obj)>0
class ProductDetailSerializer(ProductListSerializer):
    variants=VariantSerializer(many=True,read_only=True); images=ProductImageSerializer(many=True,read_only=True)
    beauty_profile=BeautyProfileSerializer(read_only=True); claims=serializers.SerializerMethodField()
    class Meta(ProductListSerializer.Meta): fields=ProductListSerializer.Meta.fields+("short_description","description","weight","tax_class","variants","images","beauty_profile","claims","published_at")
    def get_claims(self,obj): return ProductClaimSerializer([pc for pc in obj.product_claims.all() if pc.active],many=True).data

class ProductAdminSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)

    class Meta: model=Product; fields="__all__"; read_only_fields=("uuid","published_at")
    def validate(self,attrs):
        ptype=attrs.get("product_type",getattr(self.instance,"product_type",None)); sku=attrs.get("sku",getattr(self.instance,"sku",None)); status=attrs.get("status",getattr(self.instance,"status",Product.Status.DRAFT))
        if self.instance and "product_type" in attrs and attrs["product_type"]!=self.instance.product_type: raise serializers.ValidationError({"product_type":"Product type is immutable after creation; create a new product to change stock identity."})
        if ptype==Product.ProductType.SIMPLE and not sku: raise serializers.ValidationError({"sku":"SKU is required for simple products."})
        if self.instance and ptype==Product.ProductType.SIMPLE and self.instance.variants.exists(): raise serializers.ValidationError({"product_type":"Remove variants before converting to simple."})
        if status==Product.Status.ACTIVE and ptype==Product.ProductType.VARIABLE:
            if self.instance is None or not self.instance.variants.filter(is_active=True).exists():
                raise serializers.ValidationError({"status":"Create variable products as draft; at least one active variant is required before publishing."})
        return attrs
class VariantAdminSerializer(serializers.ModelSerializer):
    attribute_value_ids=serializers.PrimaryKeyRelatedField(source="attributes",many=True,queryset=AttributeValue.objects.all(),write_only=True,required=False)
    class Meta: model=ProductVariant; fields=("id","uuid","product","sku","barcode","price_override","cost_price","weight","is_active","attribute_value_ids")
    def validate_product(self,product):
        if product.product_type!=Product.ProductType.VARIABLE: raise serializers.ValidationError("Variants are only valid for variable products.")
        return product
    def validate(self,attrs):
        values=attrs.get("attributes")
        if values:
            ids=[v.attribute_id for v in values]
            if len(ids)!=len(set(ids)): raise serializers.ValidationError({"attribute_value_ids":"Only one value per attribute is allowed."})
            product=attrs.get("product",getattr(self.instance,"product",None)); value_ids=sorted(v.id for v in values)
            if product:
                for variant in product.variants.exclude(pk=getattr(self.instance,"pk",None)).prefetch_related("attributes"):
                    if sorted(variant.attributes.values_list("id",flat=True))==value_ids: raise serializers.ValidationError({"attribute_value_ids":"This variant attribute combination already exists."})
        return attrs

class AttributeAdminSerializer(serializers.ModelSerializer):
    class Meta: model=Attribute; fields="__all__"
class AttributeValueAdminSerializer(serializers.ModelSerializer):
    class Meta: model=AttributeValue; fields="__all__"
class ClaimAdminSerializer(serializers.ModelSerializer):
    class Meta: model=Claim; fields="__all__"
class ProductClaimAdminSerializer(serializers.ModelSerializer):
    class Meta: model=ProductClaim; fields="__all__"
class BeautyProfileAdminSerializer(serializers.ModelSerializer):
    class Meta: model=ProductBeautyProfile; fields="__all__"


class SkinTypeAdminSerializer(serializers.ModelSerializer):
    class Meta: model=SkinType; fields="__all__"
class HairTypeAdminSerializer(serializers.ModelSerializer):
    class Meta: model=HairType; fields="__all__"
class ConcernAdminSerializer(serializers.ModelSerializer):
    class Meta: model=Concern; fields="__all__"
class IngredientAdminSerializer(serializers.ModelSerializer):
    class Meta: model=Ingredient; fields="__all__"
