from django.test import TestCase
from rest_framework.test import APIClient

from apps.tracking.models import TrackingSettings


class TrackingPublicConfigTests(TestCase):
    def test_public_config_never_exposes_access_token(self):
        TrackingSettings.objects.create(pk=1, enabled=True, meta_pixel_id="123")
        response = APIClient().get("/api/v1/tracking/config/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("meta_access_token", response.json().get("data", {}))
        self.assertNotIn("meta_access_token_encrypted", response.json().get("data", {}))
