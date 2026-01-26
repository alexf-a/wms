"""Management command to create a single beta user.

This command creates a beta user with a specified email and password.
The user will be required to change their password on first login.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    """Create a beta user with specified email and password."""

    help = "Create a beta user for closed beta testing"

    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument("email", type=str, help="User email address")
        parser.add_argument("password", type=str, help="User password")
        parser.add_argument(
            "--superuser",
            action="store_true",
            help="Create as superuser (default: regular user)",
        )

    def handle(self, *args, **options):
        """Create a beta user with the specified credentials.

        Args:
            email: Email address for the user
            password: Initial password (user will be forced to change)
            superuser: Whether to create as superuser (default: False)
        """
        User = get_user_model()
        email = options["email"]
        password = options["password"]
        is_superuser = options["superuser"]

        # Check if user already exists
        if User.objects.filter(email=email).exists():
            self.stdout.write(
                self.style.WARNING(f"User with email {email} already exists")
            )
            return

        # Create user
        if is_superuser:
            user = User.objects.create_superuser(email=email, password=password)
            # Superusers don't need to change password
            user.must_change_password = False
            user.save()
            self.stdout.write(
                self.style.SUCCESS(f"Superuser {email} created successfully")
            )
        else:
            user = User.objects.create_user(email=email, password=password)
            # Beta users must change password on first login
            user.must_change_password = True
            user.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Beta user {email} created successfully (must change password on first login)"
                )
            )
