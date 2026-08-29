from cryptography.fernet import Fernet
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.payments.gateway_config import is_payment_method_available
from apps.payments.models import Payment, PaymentGatewayConfig
from apps.payments.serializers import PaymentGatewayConfigSerializer


@override_settings(PAYMENT_CONFIG_ENCRYPTION_KEY=Fernet.generate_key().decode())
class PaymentGatewayConfigTests(TestCase):
    def setUp(self):
        self.gateway, _ = PaymentGatewayConfig.objects.update_or_create(
            provider=PaymentGatewayConfig.Provider.SSLCOMMERZ,
            defaults={
                "display_name": "SSLCOMMERZ",
                "sandbox_mode": True,
                "is_active": False,
                "sort_order": 10,
                "sandbox_config_encrypted": "",
                "live_config_encrypted": "",
            },
        )

    def test_credentials_are_encrypted_and_secrets_are_not_serialized(self):
        self.gateway.set_environment_config("sandbox", {"store_id": "sandbox-store", "store_password": "very-secret"})
        self.gateway.save()
        self.gateway.refresh_from_db()

        self.assertNotIn("very-secret", self.gateway.sandbox_config_encrypted)
        self.assertEqual(self.gateway.get_environment_config("sandbox")["store_password"], "very-secret")

        payload = PaymentGatewayConfigSerializer(self.gateway).data
        self.assertEqual(payload["sandbox_values"]["store_id"], "sandbox-store")
        self.assertNotIn("store_password", payload["sandbox_values"])
        self.assertTrue(payload["sandbox_field_status"]["store_password"])

    def test_gateway_can_be_activated_only_after_selected_environment_is_configured(self):
        invalid = PaymentGatewayConfigSerializer(self.gateway, data={"is_active": True}, partial=True)
        self.assertFalse(invalid.is_valid())

        valid = PaymentGatewayConfigSerializer(
            self.gateway,
            data={
                "is_active": True,
                "sandbox_mode": True,
                "sandbox_config": {"store_id": "sandbox-store", "store_password": "sandbox-password"},
            },
            partial=True,
        )
        self.assertTrue(valid.is_valid(), valid.errors)
        valid.save()
        self.assertTrue(is_payment_method_available(Payment.Method.SSLCOMMERZ))

    def test_public_methods_include_only_active_configured_gateways(self):
        client = APIClient()
        response = client.get("/api/v1/payment-methods/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["code"] for row in response.data["data"]], ["cod"])

        self.gateway.set_environment_config("sandbox", {"store_id": "sandbox-store", "store_password": "sandbox-password"})
        self.gateway.is_active = True
        self.gateway.save()
        response = client.get("/api/v1/payment-methods/")
        codes = [row["code"] for row in response.data["data"]]
        self.assertEqual(codes, ["cod", "sslcommerz"])
        self.assertEqual(response.data["data"][1]["environment"], "sandbox")
