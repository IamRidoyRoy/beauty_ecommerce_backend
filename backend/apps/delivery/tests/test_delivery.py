from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from apps.delivery.models import City, DeliveryModule, Thana


class DeliveryTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.inside = DeliveryModule.objects.create(name="Inside Dhaka", code="inside_dhaka", charge=Decimal("60"), sort_order=10)
        self.outside = DeliveryModule.objects.create(name="Outside Dhaka", code="outside_dhaka", charge=Decimal("120"), sort_order=30)
        self.subarea = DeliveryModule.objects.create(name="Subarea", code="subarea", charge=Decimal("90"), sort_order=20)
        self.dhaka = City.objects.create(name="Dhaka", delivery_module=self.inside)
        self.dhanmondi = Thana.objects.create(city=self.dhaka, name="Dhanmondi")
        self.savar = Thana.objects.create(city=self.dhaka, name="Savar", delivery_module=self.subarea)
        self.chittagong = City.objects.create(name="Chittagong", delivery_module=self.outside)
        self.panchlaish = Thana.objects.create(city=self.chittagong, name="Panchlaish")

    def test_district_dropdown_and_dependent_thanas(self):
        districts = self.client.get("/api/v1/districts/")
        self.assertEqual(districts.status_code, 200)
        names = [row["name"] for row in districts.data["data"]]
        self.assertIn("Dhaka", names)
        thanas = self.client.get(f"/api/v1/districts/{self.dhaka.id}/thanas/")
        self.assertEqual(thanas.status_code, 200)
        self.assertEqual({row["name"] for row in thanas.data["data"]}, {"Dhanmondi", "Savar"})

    def test_delivery_quote_uses_city_module_and_thana_override(self):
        inside = self.client.get(f"/api/v1/delivery-charge/?district={self.dhaka.id}&thana={self.dhanmondi.id}")
        self.assertEqual(inside.status_code, 200)
        self.assertEqual(inside.data["data"]["charge"], "60.00")
        subarea = self.client.get(f"/api/v1/delivery-charge/?district={self.dhaka.id}&thana={self.savar.id}")
        self.assertEqual(subarea.data["data"]["charge"], "90.00")
        outside = self.client.get(f"/api/v1/delivery-charge/?district={self.chittagong.id}&thana={self.panchlaish.id}")
        self.assertEqual(outside.data["data"]["charge"], "120.00")

    def test_import_command_is_idempotent(self):
        # Use a clean geography because the command imports source ids/names.
        Thana.objects.all().delete()
        City.objects.all().delete()
        call_command("import_delivery_data")
        first = (City.objects.count(), Thana.objects.count())
        call_command("import_delivery_data")
        second = (City.objects.count(), Thana.objects.count())
        self.assertEqual(first, (71, 785))
        self.assertEqual(second, first)
        self.assertEqual(DeliveryModule.objects.get(code="inside_dhaka").charge, Decimal("60.00"))
        self.assertEqual(DeliveryModule.objects.get(code="subarea").charge, Decimal("90.00"))
        self.assertEqual(DeliveryModule.objects.get(code="outside_dhaka").charge, Decimal("120.00"))
