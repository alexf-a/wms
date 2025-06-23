from django.core.management.base import BaseCommand
from core.models import Bin


class Command(BaseCommand):
    help = "Delete all bins from the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Confirm deletion without prompting",
        )

    def handle(self, *args, **options):
        bin_count = Bin.objects.count()

        if bin_count == 0:
            self.stdout.write(self.style.SUCCESS("No bins found in the database."))
            return

        self.stdout.write(f"Found {bin_count} bins in the database.")

        if not options["confirm"]:
            confirm = input("Are you sure you want to delete ALL bins? This action cannot be undone. (yes/no): ")
            if confirm.lower() != "yes":
                self.stdout.write(self.style.WARNING("Operation cancelled."))
                return

        # Delete all bins
        deleted_count, _ = Bin.objects.all().delete()

        self.stdout.write(
            self.style.SUCCESS(f"Successfully deleted {deleted_count} bins from the database.")
        )
