from django.core.management.base import BaseCommand
from apps.common.models import AnnouncementMessage

DEFAULTS = [
    {"text": "Beauty deals updated daily — discover today’s offers", "icon": "gift", "link_url": "/products?ordering=-compare_at_price", "order": 1},
    {"text": "100% authentic beauty products", "icon": "badge", "link_url": "", "order": 2},
    {"text": "Free delivery on eligible orders over ৳2,000", "icon": "truck", "link_url": "", "order": 3},
    {"text": "New arrivals, trending skincare & makeup every week", "icon": "sparkles", "link_url": "/products?new_arrival=true", "order": 4},
]


class Command(BaseCommand):
    help = "Create the default storefront announcement-bar messages without duplicating existing text."

    def handle(self, *args, **options):
        created = 0
        for row in DEFAULTS:
            _, was_created = AnnouncementMessage.objects.get_or_create(
                text=row["text"],
                defaults={**row, "active": True},
            )
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"Announcement messages ready. Created {created}."))
