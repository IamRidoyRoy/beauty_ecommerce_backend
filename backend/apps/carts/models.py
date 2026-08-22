import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from apps.common.models import TimeStampedModel
from apps.catalog.models import Product,ProductVariant
class Cart(TimeStampedModel):
    token=models.UUIDField(default=uuid.uuid4,unique=True,editable=False,db_index=True)
    user=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.CASCADE,related_name="carts")
    is_active=models.BooleanField(default=True,db_index=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["user"],condition=Q(user__isnull=False,is_active=True),name="one_active_cart_per_user")]
class CartItem(TimeStampedModel):
    cart=models.ForeignKey(Cart,on_delete=models.CASCADE,related_name="items")
    product=models.ForeignKey(Product,null=True,blank=True,on_delete=models.CASCADE,related_name="cart_items")
    product_variant=models.ForeignKey(ProductVariant,null=True,blank=True,on_delete=models.CASCADE,related_name="cart_items")
    quantity=models.PositiveIntegerField(default=1)
    class Meta:
        constraints=[
            models.CheckConstraint(condition=(Q(product__isnull=False,product_variant__isnull=True)|Q(product__isnull=True,product_variant__isnull=False)),name="cart_item_exactly_one_target"),
            models.CheckConstraint(condition=Q(quantity__gt=0),name="cart_item_quantity_gt_zero"),
            models.UniqueConstraint(fields=["cart","product"],condition=Q(product__isnull=False),name="unique_cart_simple_product"),
            models.UniqueConstraint(fields=["cart","product_variant"],condition=Q(product_variant__isnull=False),name="unique_cart_variant"),
        ]
    @property
    def unit_price(self): return self.product.base_price if self.product_id else self.product_variant.selling_price
    @property
    def line_total(self): return self.unit_price*self.quantity
