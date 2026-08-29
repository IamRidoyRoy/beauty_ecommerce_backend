from django.conf import settings
from django.db import models
from django.db.models import Q
from apps.common.models import TimeStampedModel,UUIDModel
from apps.catalog.models import Product,ProductVariant
class Order(TimeStampedModel,UUIDModel):
    class Status(models.TextChoices):
        PENDING="pending","Pending"; CONFIRMED="confirmed","Confirmed"; PROCESSING="processing","Processing"; PACKED="packed","Packed"; SHIPPED="shipped","Shipped"; OUT_FOR_DELIVERY="out_for_delivery","Out For Delivery"; DELIVERED="delivered","Delivered"; CANCELLED="cancelled","Cancelled"; RETURN_REQUESTED="return_requested","Return Requested"; RETURNED="returned","Returned"; PARTIALLY_RETURNED="partially_returned","Partially Returned"; REFUNDED="refunded","Refunded"
    class PaymentStatus(models.TextChoices): PENDING="pending","Pending"; PAID="paid","Paid"; FAILED="failed","Failed"; PARTIAL_REFUND="partial_refund","Partially Refunded"; REFUNDED="refunded","Refunded"
    class FulfillmentStatus(models.TextChoices): UNFULFILLED="unfulfilled","Unfulfilled"; PROCESSING="processing","Processing"; FULFILLED="fulfilled","Fulfilled"; PARTIAL_RETURN="partial_return","Partially Returned"; RETURNED="returned","Returned"
    order_number=models.CharField(max_length=40,unique=True,db_index=True)
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="orders")
    customer_name=models.CharField(max_length=180); customer_phone=models.CharField(max_length=24,db_index=True); shipping_address_snapshot=models.JSONField(default=dict)
    shipping_method=models.ForeignKey("shipping.ShippingMethod",null=True,on_delete=models.SET_NULL,related_name="orders")
    coupon_code_snapshot=models.CharField(max_length=60,blank=True); promotion_snapshot=models.JSONField(default=list,blank=True)
    subtotal=models.DecimalField(max_digits=14,decimal_places=2); discount=models.DecimalField(max_digits=14,decimal_places=2,default=0); shipping_charge=models.DecimalField(max_digits=12,decimal_places=2,default=0); tax=models.DecimalField(max_digits=12,decimal_places=2,default=0); total=models.DecimalField(max_digits=14,decimal_places=2)
    order_status=models.CharField(max_length=30,choices=Status.choices,default=Status.PENDING,db_index=True); payment_status=models.CharField(max_length=24,choices=PaymentStatus.choices,default=PaymentStatus.PENDING,db_index=True); fulfillment_status=models.CharField(max_length=24,choices=FulfillmentStatus.choices,default=FulfillmentStatus.UNFULFILLED,db_index=True)
    notes=models.TextField(blank=True)
    class Meta:
        indexes=[models.Index(fields=["created_at","order_status"]),models.Index(fields=["user","created_at"]),models.Index(fields=["customer_phone","created_at"]),models.Index(fields=["payment_status","created_at"])]
class OrderItem(TimeStampedModel):
    order=models.ForeignKey(Order,on_delete=models.CASCADE,related_name="items")
    product=models.ForeignKey(Product,null=True,on_delete=models.SET_NULL,related_name="order_items")
    variant=models.ForeignKey(ProductVariant,null=True,blank=True,on_delete=models.SET_NULL,related_name="order_items")
    product_name_snapshot=models.CharField(max_length=220); sku_snapshot=models.CharField(max_length=100); variant_snapshot=models.JSONField(default=dict,blank=True); image_snapshot=models.CharField(max_length=500,blank=True)
    quantity=models.PositiveIntegerField(); unit_price=models.DecimalField(max_digits=12,decimal_places=2); discount=models.DecimalField(max_digits=12,decimal_places=2,default=0); tax=models.DecimalField(max_digits=12,decimal_places=2,default=0); total=models.DecimalField(max_digits=14,decimal_places=2); cost_price_snapshot=models.DecimalField(max_digits=12,decimal_places=2,default=0)
    returned_quantity=models.PositiveIntegerField(default=0)
    class Meta:
        constraints=[models.CheckConstraint(condition=Q(quantity__gt=0),name="order_item_qty_gt_zero"),models.CheckConstraint(condition=Q(returned_quantity__lte=models.F("quantity")),name="order_item_returned_lte_qty")]
        indexes=[models.Index(fields=["product","order"]),models.Index(fields=["sku_snapshot"])]
