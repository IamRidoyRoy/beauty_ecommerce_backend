from django.db import migrations, models


def normalize_packed_workflow(apps, schema_editor):
    CourierConfig = apps.get_model("shipping", "CourierConfig")
    CourierConfig.objects.exclude(auto_book_order_status="packed").update(auto_book_order_status="packed")

    # The orders app predates the committed migration baseline in this project,
    # so normalize legacy rows with a guarded SQL update instead of depending on
    # a historical Order model state that may not exist in the migration graph.
    connection = schema_editor.connection
    table = "orders_order"
    if table in connection.introspection.table_names():
        qn = connection.ops.quote_name
        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {qn(table)} SET {qn('order_status')} = %s WHERE {qn('order_status')} = %s",
                ["packed", "ready_to_ship"],
            )


class Migration(migrations.Migration):
    dependencies = [
        ("shipping", "0003_carrybee"),
    ]

    operations = [
        migrations.AlterField(
            model_name="courierconfig",
            name="auto_book_order_status",
            field=models.CharField(default="packed", max_length=30),
        ),
        migrations.RunPython(normalize_packed_workflow, migrations.RunPython.noop),
    ]
