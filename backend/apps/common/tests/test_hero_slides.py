from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.common.models import HeroSlide


@override_settings(MEDIA_ROOT="/tmp/beauty-test-media")
class HeroSlidePublicApiTests(APITestCase):
    def _image(self, name="hero.gif"):
        return SimpleUploadedFile(name, b"GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;", content_type="image/gif")

    def test_only_current_active_slides_are_public(self):
        now = timezone.now()
        HeroSlide.objects.create(title="Live", image=self._image("live.gif"), active=True, order=2)
        HeroSlide.objects.create(title="Hidden", image=self._image("hidden.gif"), active=False, order=1)
        HeroSlide.objects.create(title="Future", image=self._image("future.gif"), active=True, starts_at=now + timedelta(days=1))
        HeroSlide.objects.create(title="Expired", image=self._image("expired.gif"), active=True, ends_at=now - timedelta(days=1))

        response = self.client.get("/api/v1/hero-slides/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual([slide["title"] for slide in payload], ["Live"])
        self.assertTrue(payload[0]["image"].startswith("/media/"))
