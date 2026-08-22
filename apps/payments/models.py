from django.db import models
from apps.common.models import TimeStampedModel
class Payment(TimeStampedModel):
    class Method(models.TextChoices): COD="cod","COD"; BKASH="bkash","bKash"; NAGAD="nagad","Nagad"; CARD="card","Card"
    class Status(models.TextChoices): PENDING="pending","Pending"; AUTHORIZED="authorized","Authorized"; PAID="paid","Paid"; FAILED="failed","Failed"; CANCELLED="cancelled","Cancelled"; PARTIAL_REFUND="partial_refund","Partially Refunded"; REFUNDED="refunded","Refunded"
    order=models.ForeignKey("orders.Order",on_delete=models.CASCADE,related_name="payments"); method=models.CharField(max_length=20,choices=Method.choices); transaction_id=models.CharField(max_length=120,blank=True,db_index=True); gateway_reference=models.CharField(max_length=180,blank=True,db_index=True); amount=models.DecimalField(max_digits=14,decimal_places=2); status=models.CharField(max_length=24,choices=Status.choices,default=Status.PENDING,db_index=True); paid_at=models.DateTimeField(null=True,blank=True); metadata=models.JSONField(default=dict,blank=True)
class PaymentWebhookEvent(TimeStampedModel):
    provider=models.CharField(max_length=30); event_id=models.CharField(max_length=180); payload=models.JSONField(default=dict); processed_at=models.DateTimeField(null=True,blank=True); processing_error=models.TextField(blank=True)
    class Meta: constraints=[models.UniqueConstraint(fields=["provider","event_id"],name="unique_payment_webhook_event")]
