from django.db import migrations, models


def seed_announcements(apps, schema_editor):
    Item=apps.get_model("siteconfig","AnnouncementItem")
    defaults=[
        {"text":"Beauty deals updated daily — discover today’s offers","icon":"gift","link_type":"products","link_value":"","active":True,"order":10},
        {"text":"100% authentic beauty products","icon":"badge","link_type":"none","link_value":"","active":True,"order":20},
        {"text":"Free delivery on eligible orders over ৳2,000","icon":"truck","link_type":"products","link_value":"","active":True,"order":30},
        {"text":"New arrivals, trending skincare & makeup every week","icon":"sparkles","link_type":"products","link_value":"new_arrival=true","active":True,"order":40},
    ]
    for row in defaults:
        Item.objects.get_or_create(text=row["text"],defaults=row)


class Migration(migrations.Migration):
    dependencies=[("siteconfig","0002_homepage_banner")]
    operations=[
        migrations.CreateModel(
            name="AnnouncementItem",
            fields=[
                ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
                ("text",models.CharField(max_length=220)),
                ("icon",models.CharField(choices=[("gift","Gift"),("badge","Authenticity badge"),("truck","Delivery truck"),("sparkles","Sparkles"),("tag","Offer tag")],default="sparkles",max_length=16)),
                ("link_type",models.CharField(choices=[("none","No link"),("custom","Custom route / URL"),("products","Products page"),("category","Category"),("brand","Brand"),("product","Product"),("search","Search query")],default="none",max_length=16)),
                ("link_value",models.CharField(blank=True,max_length=500)),
                ("active",models.BooleanField(db_index=True,default=True)),
                ("order",models.PositiveIntegerField(db_index=True,default=0)),
                ("created_at",models.DateTimeField(auto_now_add=True)),
                ("updated_at",models.DateTimeField(auto_now=True)),
            ],
            options={"ordering":("order","id")},
        ),
        migrations.RunPython(seed_announcements,migrations.RunPython.noop),
    ]
