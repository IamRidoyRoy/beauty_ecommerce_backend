from .models import Notification
from .tasks import send_notification
def queue_notification(*,channel,body,user=None,subject="",metadata=None):
    n=Notification.objects.create(user=user,channel=channel,body=body,subject=subject,metadata=metadata or {}); send_notification.delay(n.id); return n
