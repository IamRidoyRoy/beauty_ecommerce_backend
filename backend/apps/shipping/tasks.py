from celery import shared_task

from .services import auto_book_order, auto_book_ready_orders, sync_open_shipments


@shared_task
def auto_book_courier_orders():
    return auto_book_ready_orders()


@shared_task
def sync_courier_shipments():
    return sync_open_shipments()


@shared_task
def auto_book_courier_order(order_id: int):
    return auto_book_order(order_id)
