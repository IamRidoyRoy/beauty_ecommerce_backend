from unittest.mock import patch

from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import OTPChallenge, User
from apps.accounts.throttles import OTPRateThrottle


@override_settings(DEBUG=True)
class OTPLoginTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone="01779714999", full_name="OTP Customer")

    @patch("apps.accounts.views.queue_notification")
    def test_request_and_verify_otp(self, queue_notification):
        request_response = self.client.post(
            "/api/v1/auth/otp/request/",
            {"phone": "01779714999"},
            format="json",
        )
        self.assertEqual(request_response.status_code, 200)
        code = request_response.data["data"]["development_otp"]
        self.assertEqual(len(code), 6)
        challenge = OTPChallenge.objects.latest("id")
        self.assertEqual(challenge.debug_code, code)

        verify_response = self.client.post(
            "/api/v1/auth/otp/verify/",
            {"phone": "01779714999", "code": code},
            format="json",
        )
        self.assertEqual(verify_response.status_code, 200)
        self.assertIn("access", verify_response.data["data"]["auth"])
        self.assertIn("refresh", verify_response.data["data"]["auth"])

        self.user.refresh_from_db()
        self.assertTrue(self.user.phone_verified)

    @patch("apps.accounts.views.queue_notification", side_effect=RuntimeError("Celery unavailable"))
    def test_debug_otp_request_survives_notification_failure(self, queue_notification):
        response = self.client.post(
            "/api/v1/auth/otp/request/",
            {"phone": "01779714999"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("development_otp", response.data["data"])


    def test_otp_rate_supports_five_requests_per_ten_minutes(self):
        throttle = OTPRateThrottle()
        self.assertEqual(throttle.num_requests, 5)
        self.assertEqual(throttle.duration, 600)

    @override_settings(DEBUG=False)
    def test_production_does_not_store_readable_otp(self):
        from apps.accounts.services import create_otp

        create_otp(self.user.phone)
        challenge = OTPChallenge.objects.latest("id")
        self.assertEqual(challenge.debug_code, "")
