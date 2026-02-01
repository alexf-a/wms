"""Management command to ensure a superuser exists.

This command is designed for container deployments where shell access is not available.
It reads DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD from environment variables
and creates a superuser if one doesn't already exist with that email.
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Ensure a superuser exists for initial deployment setup."""

    help = "Ensure a superuser exists (reads credentials from environment variables)"

    def handle(self, *args, **options):
        """Create superuser from environment variables if not exists.

        Reads DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD from environment.
        If both are set and no user with that email exists, creates a superuser.
        """
        User = get_user_model()
        email = os.getenv("DJANGO_SUPERUSER_EMAIL")
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD")

        if not email:
            self.stdout.write(
                self.style.NOTICE("DJANGO_SUPERUSER_EMAIL not set, skipping superuser creation")
            )
            return

        if not password:
            self.stdout.write(
                self.style.NOTICE("DJANGO_SUPERUSER_PASSWORD not set, skipping superuser creation")
            )
            return

        if User.objects.filter(email=email).exists():
            self.stdout.write(self.style.SUCCESS(f"Superuser with email {email} already exists"))
            return

        User.objects.create_superuser(email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Superuser {email} created successfully"))
