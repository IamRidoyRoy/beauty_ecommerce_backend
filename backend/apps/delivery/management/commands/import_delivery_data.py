import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.delivery.models import City, DeliveryModule, Thana


MODULES = {
    1: {
        "code": DeliveryModule.Code.INSIDE_DHAKA,
        "name": "Inside Dhaka",
        "charge": "60.00",
        "sort_order": 10,
    },
    2: {
        "code": DeliveryModule.Code.OUTSIDE_DHAKA,
        "name": "Outside Dhaka",
        "charge": "120.00",
        "sort_order": 30,
    },
    3: {
        "code": DeliveryModule.Code.SUBAREA,
        "name": "Subarea",
        "charge": "90.00",
        "sort_order": 20,
    },
}


class Command(BaseCommand):
    help = "Import the bundled district/city and thana JSON and seed the 3 delivery modules."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing cities/thanas before importing. Delivery modules are updated, not deleted.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        data_dir = Path(__file__).resolve().parents[2] / "data"
        city_file = data_dir / "city.json"
        thana_file = data_dir / "thana.json"
        if not city_file.exists() or not thana_file.exists():
            raise CommandError("Bundled city.json or thana.json is missing.")

        if options["reset"]:
            Thana.objects.all().delete()
            City.objects.all().delete()

        module_map = {}
        for legacy_id, values in MODULES.items():
            module, _ = DeliveryModule.objects.update_or_create(
                code=values["code"],
                defaults={
                    "name": values["name"],
                    "charge": values["charge"],
                    "sort_order": values["sort_order"],
                    "active": True,
                },
            )
            module_map[legacy_id] = module

        city_rows = json.loads(city_file.read_text(encoding="utf-8"))
        thana_rows = json.loads(thana_file.read_text(encoding="utf-8"))

        imported_cities = {}
        city_created = city_updated = 0
        for row in city_rows:
            source_id = int(row["pk"])
            fields = row["fields"]
            legacy_module_id = int(fields.get("delivery_module") or 2)
            module = module_map.get(legacy_module_id, module_map[2])
            name = fields["name"].strip()
            city = City.objects.filter(source_id=source_id).first()
            created = False
            if city is None:
                city = City.objects.filter(name__iexact=name, source_id__isnull=True).first()
            if city is None:
                city = City.objects.create(source_id=source_id, name=name, delivery_module=module, active=True)
                created = True
            else:
                city.source_id = source_id
                city.name = name
                city.delivery_module = module
                city.active = True
                city.save(update_fields=["source_id", "name", "delivery_module", "active", "updated_at"])
            imported_cities[source_id] = city
            city_created += int(created)
            city_updated += int(not created)

        thana_created = thana_updated = 0
        for row in thana_rows:
            source_id = int(row["pk"])
            fields = row["fields"]
            source_city_id = int(fields["city"])
            city = imported_cities.get(source_city_id)
            if not city:
                raise CommandError(f"Thana source id {source_id} references missing city {source_city_id}.")
            name = fields["name"].strip()
            thana = Thana.objects.filter(source_id=source_id).first()
            created = False
            if thana is None:
                thana = Thana.objects.filter(city=city, name__iexact=name, source_id__isnull=True).first()
            if thana is None:
                thana = Thana.objects.create(source_id=source_id, city=city, name=name, active=True)
                created = True
            else:
                thana.source_id = source_id
                thana.city = city
                thana.name = name
                thana.active = True
                thana.save(update_fields=["source_id", "city", "name", "active", "updated_at"])
            thana_created += int(created)
            thana_updated += int(not created)

        self.stdout.write(self.style.SUCCESS(
            f"Delivery import complete: cities {city_created} created/{city_updated} updated; "
            f"thanas {thana_created} created/{thana_updated} updated."
        ))
        self.stdout.write(
            "Pricing seeded: Inside Dhaka=৳60, Subarea=৳90, Outside Dhaka=৳120. "
            "The supplied JSON only marks Dhaka vs outside Dhaka; assign the Subarea module to selected thanas from Django Admin/API."
        )
