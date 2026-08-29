from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="SiteBrandingSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("website_brand_mode", models.CharField(choices=[("text", "Text name"), ("logo", "Logo image")], default="text", max_length=8)),
                ("website_name", models.CharField(default="LUMÉA", max_length=120)),
                ("website_tagline", models.CharField(blank=True, default="Beauty Commerce", max_length=160)),
                ("website_logo", models.ImageField(blank=True, null=True, upload_to="branding/website/")),
                ("dashboard_brand_mode", models.CharField(choices=[("text", "Text name"), ("logo", "Logo image")], default="text", max_length=8)),
                ("dashboard_name", models.CharField(default="BEAUTYOPS", max_length=120)),
                ("dashboard_tagline", models.CharField(blank=True, default="Commerce Control", max_length=160)),
                ("dashboard_logo", models.ImageField(blank=True, null=True, upload_to="branding/dashboard/")),
                ("primary_color", models.CharField(default="#d43a89", max_length=7)),
                ("secondary_color", models.CharField(default="#33245e", max_length=7)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"verbose_name": "Site branding setting", "verbose_name_plural": "Site branding settings"},
        )
    ]
