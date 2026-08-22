from django.conf import settings
from django.db import models
from django.db.models import Q
from apps.common.models import TimeStampedModel
class ReturnRequest(TimeStampedModel):
    class Status(models.TextChoices): REQUESTED="requested","Requested"; APPROVED="approved","Approved"; REJECTED="rejected","Rejected"; RECEIVED="received","Received"; COMPLETED="completed","Completed"
    order=models.ForeignKey("orders.Order",on_delete=models.PROTECT,related_name="return_requests"); user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="return_requests"); reason=models.TextField(); status=models.CharField(max_length=20,choices=Status.choices,default=Status.REQUESTED,db_index=True); reviewed_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="returns_reviewed"); notes=models.TextField(blank=True)
class ReturnItem(TimeStampedModel):
    return_request=models.ForeignKey(ReturnRequest,on_delete=models.CASCADE,related_name="items"); order_item=models.ForeignKey("orders.OrderItem",on_delete=models.PROTECT,related_name="return_items"); quantity=models.PositiveIntegerField(); reason=models.TextField(blank=True); restock=models.BooleanField(default=True)
    class Meta: constraints=[models.CheckConstraint(condition=Q(quantity__gt=0),name="return_item_qty_gt_zero")]
class Refund(TimeStampedModel):
    class Status(models.TextChoices): PENDING="pending","Pending"; PROCESSING="processing","Processing"; COMPLETED="completed","Completed"; FAILED="failed","Failed"; CANCELLED="cancelled","Cancelled"
    order=models.ForeignKey("orders.Order",on_delete=models.PROTECT,related_name="refunds"); payment=models.ForeignKey("payments.Payment",on_delete=models.PROTECT,related_name="refunds"); amount=models.DecimalField(max_digits=14,decimal_places=2); reason=models.TextField(blank=True); status=models.CharField(max_length=20,choices=Status.choices,default=Status.PENDING,db_index=True); gateway_reference=models.CharField(max_length=180,blank=True); created_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL,related_name="refunds_created"); completed_at=models.DateTimeField(null=True,blank=True)
    class Meta: constraints=[models.CheckConstraint(condition=Q(amount__gt=0),name="refund_amount_gt_zero")]
