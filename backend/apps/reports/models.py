from django.conf import settings
from django.db import models
from apps.common.models import TimeStampedModel
class ReportExport(TimeStampedModel):
    class Status(models.TextChoices): QUEUED="queued","Queued"; PROCESSING="processing","Processing"; COMPLETED="completed","Completed"; FAILED="failed","Failed"
    requested_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,related_name="report_exports")
    report=models.CharField(max_length=80); params=models.JSONField(default=dict,blank=True); status=models.CharField(max_length=20,choices=Status.choices,default=Status.QUEUED,db_index=True); file=models.FileField(upload_to="report_exports/%Y/%m/",blank=True); error=models.TextField(blank=True)
