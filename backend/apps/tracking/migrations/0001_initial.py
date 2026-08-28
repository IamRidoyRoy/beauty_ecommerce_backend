from django.db import migrations, models
import apps.tracking.models


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="TrackingSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("enabled", models.BooleanField(default=False)),
                ("browser_tracking_enabled", models.BooleanField(default=True)),
                ("server_tracking_enabled", models.BooleanField(default=True)),
                ("require_marketing_consent", models.BooleanField(default=False, help_text="When enabled, storefront events must carry marketing consent before browser/server tracking is sent.")),
                ("gtm_container_id", models.CharField(blank=True, max_length=40)),
                ("meta_pixel_id", models.CharField(blank=True, max_length=64)),
                ("meta_api_version", models.CharField(default="v26.0", max_length=16)),
                ("meta_access_token_encrypted", models.TextField(blank=True)),
                ("meta_test_event_code", models.CharField(blank=True, max_length=120)),
                ("currency", models.CharField(default="BDT", max_length=8)),
                ("enabled_events", models.JSONField(blank=True, default=apps.tracking.models.default_tracking_events)),
                ("last_tested_at", models.DateTimeField(blank=True, null=True)),
                ("last_test_status", models.CharField(blank=True, max_length=20)),
                ("last_test_message", models.TextField(blank=True)),
            ],
            options={"verbose_name": "Tracking setting", "verbose_name_plural": "Tracking settings"},
        ),
        migrations.CreateModel(
            name="TrackingEventLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("event_name", models.CharField(db_index=True, max_length=64)),
                ("event_id", models.CharField(db_index=True, max_length=160)),
                ("source", models.CharField(default="server", max_length=32)),
                ("status", models.CharField(choices=[("sent", "Sent"), ("failed", "Failed"), ("skipped", "Skipped")], db_index=True, max_length=16)),
                ("user_id_ref", models.PositiveBigIntegerField(blank=True, db_index=True, null=True)),
                ("order_number", models.CharField(blank=True, db_index=True, max_length=80)),
                ("http_status", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("custom_data", models.JSONField(blank=True, default=dict)),
                ("response_data", models.JSONField(blank=True, default=dict)),
                ("error_message", models.TextField(blank=True)),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AddIndex(model_name="trackingeventlog", index=models.Index(fields=["event_name", "created_at"], name="tracking_tr_event_n_2ac5cb_idx")),
        migrations.AddIndex(model_name="trackingeventlog", index=models.Index(fields=["status", "created_at"], name="tracking_tr_status_998c61_idx")),
    ]
