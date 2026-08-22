from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import F
from django.utils import timezone
from django.utils.module_loading import import_string
from apps.inventory.models import ProductStock
from .models import Notification

@shared_task
def low_stock_alerts():
    rows=ProductStock.objects.filter(available_stock__lte=F("low_stock_threshold"),warehouse__is_active=True).select_related("stock_item__product","stock_item__variant__product","warehouse")
    created=0
    for stock in rows:
        sku=stock.stock_item.product.sku if stock.stock_item.product_id else stock.stock_item.variant.sku
        Notification.objects.create(channel=Notification.Channel.INTERNAL,subject="Low stock",body=f"{sku} is low at {stock.warehouse.name}: {stock.available_stock}",metadata={"stock_id":stock.id}); created+=1
    return created

@shared_task(bind=True,autoretry_for=(RuntimeError,),retry_backoff=True,max_retries=5)
def send_notification(self,notification_id):
    n=Notification.objects.select_related("user").get(pk=notification_id)
    try:
        if n.channel==Notification.Channel.INTERNAL:
            pass
        elif n.channel==Notification.Channel.EMAIL:
            if not n.user or not n.user.email: raise RuntimeError("Notification recipient has no email.")
            send_mail(n.subject,n.body,settings.DEFAULT_FROM_EMAIL,[n.user.email],fail_silently=False)
        elif n.channel==Notification.Channel.SMS:
            phone=(n.metadata or {}).get("phone") or (n.user.phone if n.user else None)
            if not phone: raise RuntimeError("Notification recipient has no phone.")
            backend_path=getattr(settings,"SMS_BACKEND","")
            if backend_path:
                backend=import_string(backend_path)(); backend.send(phone=phone,message=n.body,metadata=n.metadata)
            elif settings.DEBUG:
                print(f"[DEV SMS] {phone}: {n.body}")
            else:
                raise RuntimeError("SMS_BACKEND is not configured.")
        else:
            raise RuntimeError(f"No provider configured for channel {n.channel}.")
        n.sent_at=timezone.now(); n.failed_at=None; n.error=""; n.save(update_fields=["sent_at","failed_at","error","updated_at"]); return n.id
    except Exception as exc:
        n.failed_at=timezone.now(); n.error=str(exc); n.save(update_fields=["failed_at","error","updated_at"]); raise

@shared_task
def send_promotional_message(user_ids,subject,body,channel="sms"):
    ids=[]
    for uid in user_ids:
        n=Notification.objects.create(user_id=uid,channel=channel,subject=subject,body=body,metadata={"campaign":True}); send_notification.delay(n.id); ids.append(n.id)
    return ids
