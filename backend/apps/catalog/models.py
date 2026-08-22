from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.text import slugify
from apps.common.models import TimeStampedModel, UUIDModel

class Category(TimeStampedModel):
    name=models.CharField(max_length=140)
    slug=models.SlugField(max_length=160, unique=True)
    parent=models.ForeignKey("self",null=True,blank=True,on_delete=models.PROTECT,related_name="children")
    image=models.ImageField(upload_to="categories/",blank=True)
    description=models.TextField(blank=True)
    active=models.BooleanField(default=True,db_index=True)
    order=models.PositiveIntegerField(default=0)
    seo=models.JSONField(default=dict,blank=True)
    class Meta:
        ordering=("order","name")
        indexes=[models.Index(fields=["parent","active","order"])]
    def __str__(self): return self.name

class Brand(TimeStampedModel):
    name=models.CharField(max_length=140,unique=True)
    slug=models.SlugField(max_length=160,unique=True)
    logo=models.ImageField(upload_to="brands/logos/",blank=True)
    cover=models.ImageField(upload_to="brands/covers/",blank=True)
    description=models.TextField(blank=True)
    country=models.CharField(max_length=100,blank=True)
    website=models.URLField(blank=True)
    featured=models.BooleanField(default=False,db_index=True)
    active=models.BooleanField(default=True,db_index=True)
    seo=models.JSONField(default=dict,blank=True)
    def __str__(self): return self.name

class SkinType(models.Model):
    name=models.CharField(max_length=80,unique=True); slug=models.SlugField(unique=True)
    def __str__(self): return self.name
class HairType(models.Model):
    name=models.CharField(max_length=80,unique=True); slug=models.SlugField(unique=True)
    def __str__(self): return self.name
class Concern(models.Model):
    name=models.CharField(max_length=100,unique=True); slug=models.SlugField(unique=True)
    concern_type=models.CharField(max_length=30,blank=True,help_text="skin/hair/body/etc")
    def __str__(self): return self.name
class Ingredient(models.Model):
    name=models.CharField(max_length=120,unique=True); slug=models.SlugField(unique=True); description=models.TextField(blank=True)
    def __str__(self): return self.name

class Product(TimeStampedModel,UUIDModel):
    class ProductType(models.TextChoices): SIMPLE="simple","Simple"; VARIABLE="variable","Variable"
    class Status(models.TextChoices): DRAFT="draft","Draft"; ACTIVE="active","Active"; ARCHIVED="archived","Archived"
    name=models.CharField(max_length=220)
    slug=models.SlugField(max_length=240,unique=True)
    product_type=models.CharField(max_length=16,choices=ProductType.choices,db_index=True)
    sku=models.CharField(max_length=100,unique=True,null=True,blank=True)
    barcode=models.CharField(max_length=100,unique=True,null=True,blank=True)
    brand=models.ForeignKey(Brand,on_delete=models.PROTECT,related_name="products")
    category=models.ForeignKey(Category,on_delete=models.PROTECT,related_name="products")
    base_price=models.DecimalField(max_digits=12,decimal_places=2,default=0)
    compare_at_price=models.DecimalField(max_digits=12,decimal_places=2,null=True,blank=True)
    cost_price=models.DecimalField(max_digits=12,decimal_places=2,null=True,blank=True)
    status=models.CharField(max_length=16,choices=Status.choices,default=Status.DRAFT,db_index=True)
    short_description=models.TextField(blank=True)
    description=models.TextField(blank=True)
    weight=models.DecimalField(max_digits=10,decimal_places=3,null=True,blank=True)
    tax_class=models.CharField(max_length=60,blank=True)
    featured=models.BooleanField(default=False,db_index=True)
    new_arrival=models.BooleanField(default=False,db_index=True)
    bestseller=models.BooleanField(default=False,db_index=True)
    trending=models.BooleanField(default=False,db_index=True)
    published_at=models.DateTimeField(null=True,blank=True,db_index=True)
    class Meta:
        indexes=[models.Index(fields=["status","category"]),models.Index(fields=["status","brand"]),models.Index(fields=["featured","status"]),models.Index(fields=["trending","status"])]
        constraints=[
            models.CheckConstraint(condition=Q(base_price__gte=0),name="product_base_price_nonnegative"),
            models.CheckConstraint(condition=Q(compare_at_price__isnull=True)|Q(compare_at_price__gte=0),name="product_compare_nonnegative"),
            models.CheckConstraint(condition=Q(cost_price__isnull=True)|Q(cost_price__gte=0),name="product_cost_nonnegative"),
        ]
    def clean(self):
        if self.product_type==self.ProductType.SIMPLE and not self.sku:
            raise ValidationError({"sku":"SKU is required for simple products."})
    def __str__(self): return self.name

class ProductBeautyProfile(TimeStampedModel):
    product=models.OneToOneField(Product,on_delete=models.CASCADE,related_name="beauty_profile")
    benefits=models.TextField(blank=True); ingredients_text=models.TextField(blank=True); how_to_use=models.TextField(blank=True); precautions=models.TextField(blank=True)
    country_of_origin=models.CharField(max_length=100,blank=True); shelf_life=models.CharField(max_length=80,blank=True); pao=models.CharField(max_length=40,blank=True)
    skin_types=models.ManyToManyField(SkinType,blank=True,related_name="profiles")
    hair_types=models.ManyToManyField(HairType,blank=True,related_name="profiles")
    concerns=models.ManyToManyField(Concern,blank=True,related_name="profiles")
    ingredients=models.ManyToManyField(Ingredient,blank=True,related_name="profiles")

class Claim(TimeStampedModel):
    name=models.CharField(max_length=120,unique=True); slug=models.SlugField(unique=True); description=models.TextField(blank=True); active=models.BooleanField(default=True)
    def __str__(self): return self.name
class ProductClaim(TimeStampedModel):
    product=models.ForeignKey(Product,on_delete=models.CASCADE,related_name="product_claims")
    claim=models.ForeignKey(Claim,on_delete=models.PROTECT,related_name="product_claims")
    is_verified=models.BooleanField(default=False)
    evidence=models.TextField(blank=True)
    source_url=models.URLField(blank=True)
    reviewed_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="reviewed_product_claims")
    reviewed_at=models.DateTimeField(null=True,blank=True)
    active=models.BooleanField(default=True)
    class Meta: constraints=[models.UniqueConstraint(fields=["product","claim"],name="unique_product_claim")]

class Attribute(TimeStampedModel):
    name=models.CharField(max_length=100,unique=True); slug=models.SlugField(unique=True); display_order=models.PositiveIntegerField(default=0)
    def __str__(self): return self.name
class AttributeValue(TimeStampedModel):
    attribute=models.ForeignKey(Attribute,on_delete=models.CASCADE,related_name="values")
    value=models.CharField(max_length=120); slug=models.SlugField(max_length=150)
    swatch=models.CharField(max_length=32,blank=True,help_text="Optional hex/color token")
    metadata=models.JSONField(default=dict,blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["attribute","slug"],name="unique_attribute_value_slug")]
    def __str__(self): return f"{self.attribute.name}: {self.value}"

class ProductVariant(TimeStampedModel,UUIDModel):
    product=models.ForeignKey(Product,on_delete=models.CASCADE,related_name="variants")
    sku=models.CharField(max_length=100,unique=True)
    barcode=models.CharField(max_length=100,unique=True,null=True,blank=True)
    price_override=models.DecimalField(max_digits=12,decimal_places=2,null=True,blank=True)
    cost_price=models.DecimalField(max_digits=12,decimal_places=2,null=True,blank=True)
    weight=models.DecimalField(max_digits=10,decimal_places=3,null=True,blank=True)
    is_active=models.BooleanField(default=True,db_index=True)
    attributes=models.ManyToManyField(AttributeValue,through="VariantAttributeValue",related_name="variants")
    class Meta:
        indexes=[models.Index(fields=["product","is_active"])]
        constraints=[models.CheckConstraint(condition=Q(price_override__isnull=True)|Q(price_override__gte=0),name="variant_price_nonnegative")]
    def clean(self):
        if self.product_id and self.product.product_type != Product.ProductType.VARIABLE:
            raise ValidationError({"product":"Variants are only allowed for variable products."})
    @property
    def selling_price(self): return self.price_override if self.price_override is not None else self.product.base_price
    def __str__(self): return self.sku

class VariantAttributeValue(models.Model):
    variant=models.ForeignKey(ProductVariant,on_delete=models.CASCADE,related_name="variant_attribute_values")
    attribute_value=models.ForeignKey(AttributeValue,on_delete=models.PROTECT,related_name="variant_attribute_values")
    class Meta: constraints=[models.UniqueConstraint(fields=["variant","attribute_value"],name="unique_variant_attribute_value")]

class ProductImage(TimeStampedModel):
    class ImageType(models.TextChoices): GALLERY="gallery","Gallery"; SWATCH="swatch","Swatch"; LIFESTYLE="lifestyle","Lifestyle"; DETAIL="detail","Detail"
    product=models.ForeignKey(Product,on_delete=models.CASCADE,related_name="images")
    variant=models.ForeignKey(ProductVariant,null=True,blank=True,on_delete=models.CASCADE,related_name="images")
    image=models.ImageField(upload_to="products/%Y/%m/")
    image_type=models.CharField(max_length=20,choices=ImageType.choices,default=ImageType.GALLERY)
    alt_text=models.CharField(max_length=220,blank=True)
    order=models.PositiveIntegerField(default=0)
    is_primary=models.BooleanField(default=False,db_index=True)
    class Meta:
        ordering=("order","id")
        indexes=[models.Index(fields=["product","variant","order"])]
        constraints=[
            models.UniqueConstraint(fields=["product"],condition=Q(is_primary=True,variant__isnull=True),name="one_primary_product_image"),
            models.UniqueConstraint(fields=["variant"],condition=Q(is_primary=True,variant__isnull=False),name="one_primary_variant_image"),
        ]
    def clean(self):
        if self.variant_id and self.variant.product_id != self.product_id:
            raise ValidationError({"variant":"Variant must belong to the selected product."})

class WishlistItem(TimeStampedModel):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="wishlist_items")
    product=models.ForeignKey(Product,on_delete=models.CASCADE,related_name="wishlisted_by")
    class Meta: constraints=[models.UniqueConstraint(fields=["user","product"],name="unique_wishlist_product")]
