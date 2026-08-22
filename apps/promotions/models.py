from django.conf import settings
from django.db import models
from django.db.models import Q
from apps.common.models import TimeStampedModel
from apps.catalog.models import Product,Brand,Category
class Coupon(TimeStampedModel):
    class Type(models.TextChoices): PERCENTAGE="percentage","Percentage"; FIXED="fixed","Fixed Amount"; FREE_SHIPPING="free_shipping","Free Shipping"
    code=models.CharField(max_length=60,unique=True,db_index=True); coupon_type=models.CharField(max_length=20,choices=Type.choices); value=models.DecimalField(max_digits=12,decimal_places=2,default=0)
    starts_at=models.DateTimeField(null=True,blank=True); ends_at=models.DateTimeField(null=True,blank=True); active=models.BooleanField(default=True,db_index=True)
    minimum_spend=models.DecimalField(max_digits=12,decimal_places=2,default=0); max_discount=models.DecimalField(max_digits=12,decimal_places=2,null=True,blank=True)
    usage_limit=models.PositiveIntegerField(null=True,blank=True); usage_limit_per_customer=models.PositiveIntegerField(null=True,blank=True); used_count=models.PositiveIntegerField(default=0); first_order_only=models.BooleanField(default=False)
    brands=models.ManyToManyField(Brand,blank=True,related_name="coupons"); categories=models.ManyToManyField(Category,blank=True,related_name="coupons"); products=models.ManyToManyField(Product,blank=True,related_name="coupons"); customers=models.ManyToManyField(settings.AUTH_USER_MODEL,blank=True,related_name="coupons")
class CouponUsage(TimeStampedModel):
    coupon=models.ForeignKey(Coupon,on_delete=models.PROTECT,related_name="usages"); user=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="coupon_usages"); order=models.OneToOneField("orders.Order",on_delete=models.CASCADE,related_name="coupon_usage")
class Promotion(TimeStampedModel):
    class Type(models.TextChoices): BOGO="bogo","BOGO"; BUY_X_GET_Y="buy_x_get_y","Buy X Get Y"; BRAND="brand_discount","Brand Discount"; CATEGORY="category_discount","Category Discount"; PRODUCT="product_discount","Product Discount"; FLASH="flash_sale","Flash Sale"; ORDER_VALUE="order_value","Order Value"; FIRST_ORDER="first_order","First Order"
    name=models.CharField(max_length=180); promotion_type=models.CharField(max_length=30,choices=Type.choices,db_index=True); active=models.BooleanField(default=True,db_index=True); starts_at=models.DateTimeField(null=True,blank=True); ends_at=models.DateTimeField(null=True,blank=True); priority=models.PositiveIntegerField(default=100); combinable=models.BooleanField(default=False); config=models.JSONField(default=dict,help_text="Auditable rule configuration")
    brands=models.ManyToManyField(Brand,blank=True,related_name="promotions"); categories=models.ManyToManyField(Category,blank=True,related_name="promotions"); products=models.ManyToManyField(Product,blank=True,related_name="promotions")
