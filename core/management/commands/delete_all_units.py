from django.core.management.base import BaseCommand

from core.models import Unit


class Command(BaseCommand):
    help = "Delete all units from the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Confirm deletion without prompting",
        )

    def handle(self, *args, **options):
        unit_count = Unit.objects.count()

        if unit_count == 0:
            self.stdout.write(self.style.SUCCESS("No units found in the database."))
            return

        self.stdout.write(f"Found {unit_count} units in the database.")

        if not options["confirm"]:
            confirm = input("Are you sure you want to delete ALL units? This action cannot be undone. (yes/no): ")
            if confirm.lower() != "yes":
                self.stdout.write(self.style.WARNING("Operation cancelled."))
                return

        # Delete all units
        deleted_count, _ = Unit.objects.all().delete()

        self.stdout.write(
            self.style.SUCCESS(f"Successfully deleted {deleted_count} units from the database.")
        )
