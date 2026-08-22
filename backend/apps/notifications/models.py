from django.conf import settings
from django.db import models
from apps.common.models import TimeStampedModel
class Notification(TimeStampedModel):
    class Channel(models.TextChoices): EMAIL="email","Email"; SMS="sms","SMS"; PUSH="push","Push"; INTERNAL="internal","Internal"
    user=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="notifications"); channel=models.CharField(max_length=20,choices=Channel.choices); subject=models.CharField(max_length=200,blank=True); body=models.TextField(); metadata=models.JSONField(default=dict,blank=True); sent_at=models.DateTimeField(null=True,blank=True); failed_at=models.DateTimeField(null=True,blank=True); error=models.TextField(blank=True)
