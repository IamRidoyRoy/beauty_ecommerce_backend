from django.db import migrations, models


def seed_homepage_banners(apps, schema_editor):
    Banner = apps.get_model("siteconfig", "HomepageBanner")
    defaults = [
        {
            "slot": "promo_left",
            "eyebrow": "Special edit",
            "title": "Glow-ready skincare",
            "subtitle": "Brightening, hydration and barrier support for everyday routines.",
            "cta_label": "Shop now",
            "link_type": "category",
            "link_value": "skincare",
            "background_color": "#3f3272",
            "text_color": "#ffffff",
            "media_background_color": "#ead7d2",
            "active": True,
        },
        {
            "slot": "promo_right",
            "eyebrow": "Special edit",
            "title": "Makeup mood refresh",
            "subtitle": "Fresh color, easy essentials and statement finishes.",
            "cta_label": "Shop now",
            "link_type": "category",
            "link_value": "makeup",
            "background_color": "#c63b8b",
            "text_color": "#ffffff",
            "media_background_color": "#f1d4e3",
            "active": True,
        },
        {
            "slot": "editorial",
            "eyebrow": "Ingredient spotlight",
            "title": "Meet niacinamide, the quiet multitasker.",
            "subtitle": "Explore formulas that support brighter-looking skin, balanced oil and a stronger-feeling barrier.",
            "cta_label": "Shop Niacinamide",
            "link_type": "search",
            "link_value": "niacinamide",
            "background_color": "#7f5c54",
            "text_color": "#ffffff",
            "media_background_color": "#ead7d2",
            "active": True,
        },
    ]
    for item in defaults:
        Banner.objects.get_or_create(slot=item["slot"], defaults=item)


class Migration(migrations.Migration):
    dependencies = [("siteconfig", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="HomepageBanner",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slot", models.CharField(choices=[("promo_left", "Promo banner — left"), ("promo_right", "Promo banner — right"), ("editorial", "Editorial / ingredient spotlight")], max_length=32, unique=True)),
                ("eyebrow", models.CharField(blank=True, max_length=120)),
                ("title", models.CharField(max_length=220)),
                ("subtitle", models.TextField(blank=True)),
                ("cta_label", models.CharField(blank=True, max_length=80)),
                ("link_type", models.CharField(choices=[("none", "No link"), ("custom", "Custom route / URL"), ("products", "Products page"), ("category", "Category"), ("brand", "Brand"), ("product", "Product"), ("search", "Search query")], default="none", max_length=16)),
                ("link_value", models.CharField(blank=True, help_text="Slug, query, or custom route depending on link type.", max_length=500)),
                ("image", models.ImageField(blank=True, null=True, upload_to="homepage/banners/")),
                ("image_alt", models.CharField(blank=True, max_length=180)),
                ("background_color", models.CharField(default="#3f3272", max_length=7)),
                ("text_color", models.CharField(default="#ffffff", max_length=7)),
                ("media_background_color", models.CharField(default="#ead7d2", max_length=7)),
                ("active", models.BooleanField(db_index=True, default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"verbose_name": "Homepage banner", "verbose_name_plural": "Homepage banners", "ordering": ("slot",)},
        ),
        migrations.RunPython(seed_homepage_banners, migrations.RunPython.noop),
    ]
