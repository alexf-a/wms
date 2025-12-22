from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from faker import Faker

from core.models import Unit
from lib.llm.claude4_xml_parser import Claude4XMLParsingError
from lib.llm.llm_handler import StructuredLangChainHandler
from lib.llm.utils import get_llm_call
from schemas.synthetic_data.unit_generation import UnitGenerationOutput


class Command(BaseCommand):
    help = "Create fake units for testing"

    def add_arguments(self, parser):
        parser.add_argument("count", type=int, help="Number of units to create")
        parser.add_argument("--username", "-u", type=str, required=True, help="Username of the owner")

    def handle(self, *args, **options):
        fake = Faker()
        user_model = get_user_model()
        username = options.get("username")
        try:
            user = user_model.objects.get(username=username)
        except user_model.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"User '{username}' not found."))
            return

        # Get the path to the LLMCall JSON file for unit generation
        unit_llm_call = get_llm_call("synthetic_data/unit_generation")

        # Create the structured handler
        unit_handler = StructuredLangChainHandler(
            llm_call=unit_llm_call,
            output_schema=UnitGenerationOutput
        )

        # Get existing unit names for this user to avoid duplicates
        existing_unit_names = set(Unit.objects.filter(user=user).values_list("name", flat=True))
        existing_names_str = ", ".join(existing_unit_names) if existing_unit_names else "None"

        count = options["count"]
        for _ in range(count):
            # Generate complete unit information using structured LLM, ensuring uniqueness
            max_attempts = 10
            unit_data = None
            for attempt in range(max_attempts):
                try:
                    # Generate complete unit using structured LLM
                    result = unit_handler.query(existing_names=existing_names_str)
                    candidate_name = result.name.strip().title()

                    # Check if name is unique (case-insensitive)
                    if candidate_name.lower() not in {name.lower() for name in existing_unit_names}:
                        unit_data = result
                        existing_unit_names.add(candidate_name)  # Add to set to avoid duplicates in this batch
                        existing_names_str = ", ".join(existing_unit_names)
                        break

                    self.stdout.write(self.style.WARNING(f"Attempt {attempt + 1}: Generated duplicate name '{candidate_name}', retrying..."))
                except Claude4XMLParsingError as e:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Attempt {attempt + 1}: XML parsing failed ({e}), retrying..."
                        )
                    )
                    continue
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Attempt {attempt + 1}: Unexpected error ({e}), retrying..."
                        )
                    )
                    continue

            if unit_data is None:
                self.stdout.write(self.style.ERROR(f"Failed to generate unique unit after {max_attempts} attempts. Skipping this unit."))
                continue

            # Post-processing of the generated data
            name = unit_data.name.strip().title()
            # Remove any special characters or numbers
            name = "".join(char for char in name if char.isalpha() or char.isspace()).strip()

            description = unit_data.description.strip()

            location = unit_data.location.strip().title()
            # Remove any special characters or numbers
            location = "".join(char for char in location if char.isalpha() or char.isspace()).strip()

            length = round(fake.random_number(digits=2) + fake.random.random(), 2)
            width = round(fake.random_number(digits=2) + fake.random.random(), 2)
            height = round(fake.random_number(digits=2) + fake.random.random(), 2)

            unit_obj = Unit(
                user=user,
                name=name,
                description=description,
                location=location,
                length=length,
                width=width,
                height=height,
            )
            unit_obj.save()

            self.stdout.write(self.style.SUCCESS(f"Created Unit:\n\n{unit_obj.name}\n\n{unit_obj.description}\n\nLocation: {unit_obj.location}"))
