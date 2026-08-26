from django.core.management import BaseCommand, call_command


class Command(BaseCommand):
    help = (
        "Create/apply migrations required by storefront control models "
        "(HeroSlide, AnnouncementMessage, CheckoutSettings) and optionally seed announcement messages."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--seed",
            action="store_true",
            help="Seed the default announcement messages after migrations are applied.",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Preparing Common/storefront-control migrations..."))
        # Generate a migration against the user's *actual* local migration graph.
        # This is safer for replace-ready dev projects than shipping a guessed
        # numbered migration that may conflict with migrations already generated locally.
        call_command("makemigrations", "common", interactive=False)

        self.stdout.write(self.style.MIGRATE_HEADING("Applying database migrations..."))
        call_command("migrate", interactive=False)

        if options.get("seed"):
            self.stdout.write(self.style.MIGRATE_HEADING("Seeding announcement messages..."))
            call_command("seed_announcement_messages")

        self.stdout.write(
            self.style.SUCCESS(
                "Storefront controls are ready. Announcement Messages can now be listed, created, edited and deleted."
            )
        )
