from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.accounts.models import User
from apps.carts.models import Cart
from apps.carts.services import add_cart_item
from apps.common.tests.utils import delivery_location, simple_product
from apps.orders.models import Order
from apps.orders.services import checkout
from apps.shipping.models import ShippingMethod

from apps.payments.gateways.base import InitiationResult, VerificationResult
from apps.payments.models import Payment, PaymentReconciliation
from apps.payments.services import initiate_gateway_payment, process_webhook, reconcile_payment


class FakeGateway:
    provider = "bkash"

    def initiate(self, *, payment, callback_url):
        return InitiationResult(
            redirect_url="https://gateway.example/checkout/PAY-1",
            gateway_reference="PAY-1",
            merchant_reference=payment.order.order_number,
            raw={"paymentID": "PAY-1"},
        )

    def verify(self, *, payment, callback_payload=None):
        return VerificationResult(
            status=Payment.Status.PAID,
            transaction_id="TRX-1",
            gateway_reference="PAY-1",
            amount=payment.amount,
            currency="BDT",
            raw={"transactionStatus": "Completed", "trxID": "TRX-1"},
        )


@override_settings(PAYMENT_API_BASE_URL="https://api.example.com", PAYMENT_STOREFRONT_URL="https://shop.example.com")
class PaymentFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone="01790000000", password="Secret123!", full_name="Payment User")
        product, _, _ = simple_product(sku="PAYMENT-SKU")
        cart = Cart.objects.create(user=self.user)
        add_cart_item(cart=cart, product=product, quantity=1)
        shipping = ShippingMethod.objects.create(name="Standard", code="standard-payment", base_charge=Decimal("0"), active=True)
        city, thana, _ = delivery_location(city_name="Payment City", thana_name="Payment Thana")
        result = checkout(
            cart=cart,
            customer_data={"name": "Payment User", "phone": self.user.phone, "district": city, "thana": thana, "address": "Test address", "label": "Home"},
            shipping_method=shipping,
            payment_method=Payment.Method.BKASH,
            request_user=self.user,
        )
        self.order = result["order"]
        self.payment = result["payment"]

    @patch("apps.payments.services.get_gateway", return_value=FakeGateway())
    def test_initiation_persists_redirect_and_gateway_reference(self, _gateway):
        payment = initiate_gateway_payment(payment=self.payment)
        self.assertEqual(payment.gateway_reference, "PAY-1")
        self.assertEqual(payment.metadata["redirect_url"], "https://gateway.example/checkout/PAY-1")
        self.assertEqual(payment.metadata["merchant_reference"], self.order.order_number)
        self.assertIsNotNone(payment.initiated_at)

    @patch("apps.payments.services.get_gateway", return_value=FakeGateway())
    def test_reconciliation_marks_payment_and_order_paid(self, _gateway):
        self.payment.gateway_reference = "PAY-1"
        self.payment.save(update_fields=["gateway_reference", "updated_at"])
        payment = reconcile_payment(payment=self.payment)
        self.order.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PAID)
        self.assertEqual(payment.transaction_id, "TRX-1")
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)
        self.assertTrue(PaymentReconciliation.objects.filter(payment=payment, success=True).exists())

    def test_webhook_event_is_idempotent(self):
        calls = []

        def handler(payload):
            calls.append(payload)

        event1, created1 = process_webhook(provider="bkash", event_id="payment:test", payload={"paymentID": "PAY-1"}, handler=handler, payment=self.payment)
        event2, created2 = process_webhook(provider="bkash", event_id="payment:test", payload={"paymentID": "PAY-1"}, handler=handler, payment=self.payment)
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(event1.pk, event2.pk)
        self.assertEqual(len(calls), 1)
