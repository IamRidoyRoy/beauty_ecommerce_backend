from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .gateways import PaymentGatewayError
from .models import Payment
from .services import is_online_payment, reconcile_payment


@shared_task
def reconcile_open_gateway_payments(limit=200):
    """Recover payments when a browser callback/IPN was delayed or missed.

    Only recently initiated, non-settled online payments are queried. Gateway
    verification remains authoritative; this task never marks a payment paid
    based on local state alone.
    """
    now = timezone.now()
    queryset = (
        Payment.objects.filter(
            initiated_at__isnull=False,
            initiated_at__gte=now - timedelta(days=3),
            initiated_at__lte=now - timedelta(minutes=2),
            status__in=[Payment.Status.PENDING, Payment.Status.AUTHORIZED],
        )
        .select_related("order")
        .order_by("last_verified_at", "initiated_at")[:limit]
    )

    checked = 0
    settled = 0
    errors = 0
    for payment in queryset:
        if not is_online_payment(payment):
            continue
        checked += 1
        previous = payment.status
        try:
            payment = reconcile_payment(payment=payment)
            if previous != Payment.Status.PAID and payment.status == Payment.Status.PAID:
                settled += 1
        except PaymentGatewayError:
            errors += 1
        except Exception:
            # A single provider/network problem must not stop reconciliation of
            # other payments in the batch.
            errors += 1
    return {"checked": checked, "settled": settled, "errors": errors}
