"""Management command to create multiple beta users from environment variables.

This command reads BETA_USER_EMAILS and BETA_USER_DEFAULT_PASSWORD from environment
variables and creates beta users for each email address.
All users will be required to change their password on first login.
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Create beta users from environment variables for deployment automation."""

    help = "Create beta users from BETA_USER_EMAILS and BETA_USER_DEFAULT_PASSWORD environment variables"

    def handle(self, *args, **options):
        """Create beta users from environment variables.

        Reads:
            BETA_USER_EMAILS: Comma-separated list of email addresses
            BETA_USER_DEFAULT_PASSWORD: Default password for all beta users
        
        All created users will have must_change_password=True.
        """
        User = get_user_model()
        emails_str = os.getenv("BETA_USER_EMAILS", "")
        password = os.getenv("BETA_USER_DEFAULT_PASSWORD")

        # Validate environment variables
        if not emails_str:
            self.stdout.write(
                self.style.NOTICE("BETA_USER_EMAILS not set, skipping beta user creation")
            )
            return

        if not password:
            self.stdout.write(
                self.style.NOTICE("BETA_USER_DEFAULT_PASSWORD not set, skipping beta user creation")
            )
            return

        # Parse email list (comma-separated)
        emails = [email.strip() for email in emails_str.split(",") if email.strip()]
        
        if not emails:
            self.stdout.write(
                self.style.NOTICE("No valid email addresses found in BETA_USER_EMAILS")
            )
            return

        # Create users
        created_count = 0
        skipped_count = 0
        
        for email in emails:
            if User.objects.filter(email=email).exists():
                self.stdout.write(
                    self.style.WARNING(f"User {email} already exists, skipping")
                )
                skipped_count += 1
                continue

            # Create beta user with must_change_password=True
            user = User.objects.create_user(email=email, password=password)
            user.must_change_password = True
            user.save()
            
            self.stdout.write(
                self.style.SUCCESS(f"Created beta user: {email}")
            )
            created_count += 1

        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f"\nBeta user creation complete: {created_count} created, {skipped_count} skipped"
            )
        )
