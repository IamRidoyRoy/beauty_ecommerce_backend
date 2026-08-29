from celery import shared_task

from .services import auto_book_order, auto_book_packed_orders, reconcile_delivered_order_statuses, sync_open_shipments


@shared_task
def auto_book_courier_orders():
    return auto_book_packed_orders()


@shared_task
def sync_courier_shipments():
    return sync_open_shipments()


@shared_task
def auto_book_courier_order(order_id: int):
    return auto_book_order(order_id)


@shared_task
def reconcile_delivered_courier_orders():
    return reconcile_delivered_order_statuses()
