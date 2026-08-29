from django.db import migrations, models


def seed_carrybee(apps, schema_editor):
    CourierConfig = apps.get_model("shipping", "CourierConfig")
    CourierConfig.objects.get_or_create(
        provider="carrybee",
        defaults={
            "display_name": "CarryBee",
            "sort_order": 40,
            "sandbox_mode": True,
            "is_active": False,
            "auto_book_enabled": False,
            "cancel_api_enabled": False,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("shipping", "0002_courier_automation"),
    ]

    operations = [
        migrations.AlterField(
            model_name="courierconfig",
            name="provider",
            field=models.CharField(
                choices=[
                    ("pathao", "Pathao"),
                    ("steadfast", "Steadfast"),
                    ("redx", "RedX"),
                    ("carrybee", "CarryBee"),
                ],
                db_index=True,
                max_length=24,
                unique=True,
            ),
        ),
        migrations.RunPython(seed_carrybee, migrations.RunPython.noop),
    ]
