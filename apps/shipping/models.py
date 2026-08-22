from django.db import models
from apps.common.models import TimeStampedModel
class ShippingMethod(TimeStampedModel):
    name=models.CharField(max_length=120); code=models.CharField(max_length=50,unique=True); base_charge=models.DecimalField(max_digits=10,decimal_places=2)
    estimated_days=models.CharField(max_length=80,blank=True); free_threshold=models.DecimalField(max_digits=12,decimal_places=2,null=True,blank=True); active=models.BooleanField(default=True,db_index=True)
    def charge_for(self,subtotal): return 0 if self.free_threshold is not None and subtotal>=self.free_threshold else self.base_charge
class Shipment(TimeStampedModel):
    class Status(models.TextChoices): PENDING="pending","Pending"; BOOKED="booked","Booked"; PICKED="picked","Picked"; IN_TRANSIT="in_transit","In Transit"; DELIVERED="delivered","Delivered"; FAILED="failed","Failed"; CANCELLED="cancelled","Cancelled"
    order=models.ForeignKey("orders.Order",on_delete=models.CASCADE,related_name="shipments"); courier=models.CharField(max_length=30,blank=True); external_id=models.CharField(max_length=120,blank=True,db_index=True); tracking_code=models.CharField(max_length=120,blank=True,db_index=True); status=models.CharField(max_length=20,choices=Status.choices,default=Status.PENDING); payload=models.JSONField(default=dict,blank=True)
