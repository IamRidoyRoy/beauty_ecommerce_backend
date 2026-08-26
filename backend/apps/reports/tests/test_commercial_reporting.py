from decimal import Decimal

from django.test import TestCase

from apps.accounts.models import User
from apps.carts.models import Cart
from apps.carts.services import add_cart_item
from apps.common.tests.utils import delivery_location, simple_product
from apps.orders.models import Order
from apps.orders.services import checkout, transition_order
from apps.reports.selectors import dashboard, profit, sales
from apps.shipping.models import ShippingMethod


class CommercialReportingRuleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone="01777777777", password="x", full_name="Report Customer")
        self.ship = ShippingMethod.objects.create(name="Report Ship", code="report-ship", base_charge=Decimal("0"))
        self.city, self.thana, _ = delivery_location()
        self.product, self.stock_item, self.warehouse = simple_product(sku="REPORT-1", stock=20)

    def place(self):
        cart = Cart.objects.create(user=self.user)
        add_cart_item(cart=cart, product=self.product, quantity=2)
        return checkout(
            cart=cart,
            customer_data={
                "name": "Report Customer",
                "phone": self.user.phone,
                "district": self.city,
                "thana": self.thana,
                "address": "Test address",
                "label": "Home",
            },
            shipping_method=self.ship,
            payment_method="cod",
            request_user=self.user,
        )["order"]

    def test_pending_order_counts_as_revenue_sales_and_profit(self):
        order = self.place()
        self.assertEqual(order.order_status, Order.Status.PENDING)
        self.assertEqual(order.payment_status, Order.PaymentStatus.PENDING)

        kpi = dashboard({})
        self.assertEqual(kpi["orders"], 1)
        self.assertEqual(kpi["revenue"], order.total)

        sales_rows = sales({})
        self.assertEqual(sum(row["orders"] for row in sales_rows), 1)
        self.assertEqual(sum(row["sales"] for row in sales_rows), order.total)

        p = profit({})
        self.assertEqual(p["orders"], 1)
        self.assertEqual(p["product_revenue"], Decimal("200.00"))
        self.assertEqual(p["cogs"], Decimal("120.00"))
        self.assertEqual(p["gross_profit"], Decimal("80.00"))

    def test_cancelled_order_is_removed_from_commercial_reports(self):
        order = self.place()
        transition_order(order=order, new_status=Order.Status.CANCELLED)

        self.assertEqual(dashboard({})["revenue"], Decimal("0"))
        self.assertEqual(sum(row["orders"] for row in sales({})), 0)
        self.assertEqual(profit({})["orders"], 0)
        self.assertEqual(profit({})["gross_profit"], Decimal("0"))

    def test_returned_order_is_removed_from_commercial_reports(self):
        order = self.place()
        # Return workflow is tested separately; direct status assignment isolates
        # the reporting rule in this test.
        order.order_status = Order.Status.RETURNED
        order.save(update_fields=["order_status", "updated_at"])

        self.assertEqual(dashboard({})["revenue"], Decimal("0"))
        self.assertEqual(sum(row["orders"] for row in sales({})), 0)
        self.assertEqual(profit({})["orders"], 0)

    def test_date_only_report_range_uses_dhaka_calendar_day(self):
        from datetime import datetime, time
        from django.utils import timezone
        from apps.reports.selectors import _range

        start, end = _range({"start": "2026-08-26", "end": "2026-08-26"})
        local_start = timezone.localtime(start)
        local_end = timezone.localtime(end)

        self.assertEqual(local_start.date().isoformat(), "2026-08-26")
        self.assertEqual(local_start.time(), time.min)
        self.assertEqual(local_end.date().isoformat(), "2026-08-26")
        self.assertEqual(local_end.hour, 23)
        self.assertEqual(local_end.minute, 59)

    def test_today_sales_includes_pending_order_created_in_dhaka_day(self):
        from datetime import datetime
        from django.utils import timezone

        order = self.place()
        local_created = timezone.make_aware(datetime(2026, 8, 26, 16, 0, 0), timezone.get_current_timezone())
        Order.objects.filter(pk=order.pk).update(created_at=local_created)

        rows = sales({"start": "2026-08-26", "end": "2026-08-26"})
        self.assertEqual(sum(row["orders"] for row in rows), 1)
        self.assertEqual(sum(row["sales"] for row in rows), order.total)
