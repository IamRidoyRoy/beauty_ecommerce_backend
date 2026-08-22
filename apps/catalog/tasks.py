from celery import shared_task
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta
from apps.common.models import AnalyticsEvent
from .models import Product
@shared_task
def recalculate_trending():
    since=timezone.now()-timedelta(hours=24)
    ids=(AnalyticsEvent.objects.filter(event_type__in=["product_view","add_to_cart"],created_at__gte=since,product_id_ref__isnull=False).values("product_id_ref").annotate(score=Count("id")).order_by("-score").values_list("product_id_ref",flat=True)[:20])
    Product.objects.update(trending=False); Product.objects.filter(id__in=list(ids)).update(trending=True)
