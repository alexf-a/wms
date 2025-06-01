from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import Bin
from faker import Faker
from pathlib import Path
from core.utils import get_qr_code_file
from llm.llm_call import LLMCall
from llm.llm_handler import StructuredLangChainHandler
from .bin_generation_schemas import BinNameOutput, BinDescriptionOutput, BinLocationOutput
from typing import cast


class Command(BaseCommand):
    help = "Create fake bins for testing"

    def add_arguments(self, parser):
        parser.add_argument("count", type=int, help="Number of bins to create")
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

        # Get the path to the LLMCall JSON files
        base_dir = Path(__file__).resolve().parent.parent.parent
        name_llm_call_path = base_dir / "llm_calls" / "bin_name_generation.json"
        desc_llm_call_path = base_dir / "llm_calls" / "bin_description_generation.json"
        location_llm_call_path = base_dir / "llm_calls" / "bin_location_generation.json"

        # Create the LLMCall instances
        name_llm_call = LLMCall.from_json(name_llm_call_path)
        desc_llm_call = LLMCall.from_json(desc_llm_call_path)
        location_llm_call = LLMCall.from_json(location_llm_call_path)

        # Create the handlers
        name_handler = StructuredLangChainHandler(llm_call=name_llm_call, output_schema=BinNameOutput)
        desc_handler = StructuredLangChainHandler(llm_call=desc_llm_call, output_schema=BinDescriptionOutput)
        location_handler = StructuredLangChainHandler(llm_call=location_llm_call, output_schema=BinLocationOutput)

        # Get existing bin names for this user to avoid duplicates
        existing_bin_names = set(Bin.objects.filter(user=user).values_list("name", flat=True))
        existing_names_str = ", ".join(existing_bin_names) if existing_bin_names else "None"

        count = options["count"]
        for _ in range(count):
            # Generate bin name using LLM, ensuring uniqueness
            max_attempts = 10
            name = None
            for attempt in range(max_attempts):
                # Generate bin name using LLM
                name_result = cast("BinNameOutput", name_handler.query(existing_names=existing_names_str))
                candidate_name = name_result.bin_name.strip().title()

                # Check if name is unique (case-insensitive)
                if candidate_name.lower() not in {name.lower() for name in existing_bin_names}:
                    name = candidate_name
                    existing_bin_names.add(name)  # Add to set to avoid duplicates in this batch
                    existing_names_str = ", ".join(existing_bin_names)
                    break

                self.stdout.write(self.style.WARNING(f"Attempt {attempt + 1}: Generated duplicate name '{candidate_name}', retrying..."))

            if name is None:
                self.stdout.write(self.style.ERROR(f"Failed to generate unique name after {max_attempts} attempts. Skipping this bin."))
                continue
            # Post-processing of the name
            name = name.strip().title()
            ## remove any special characters or numbers
            name = "".join(char for char in name if char.isalpha() or char.isspace()).strip()
            # Generate description based on generated name
            desc_result = cast("BinDescriptionOutput", desc_handler.query(bin_name=name))
            description = desc_result.description.strip()

            # Generate location using LLM based on bin name and description
            location_result = cast("BinLocationOutput", location_handler.query(bin_name=name, bin_description=description))
            location = location_result.location.strip()
            # Post-process the location
            location = location.strip().title()
            ## remove any special characters or numbers
            location = "".join(char for char in location if char.isalpha() or char.isspace()).strip()
            length = round(fake.random_number(digits=2) + fake.random.random(), 2)
            width = round(fake.random_number(digits=2) + fake.random.random(), 2)
            height = round(fake.random_number(digits=2) + fake.random.random(), 2)
            qr_code_file = get_qr_code_file(name=name, description=description, location=location, length=length, width=width, height=height)
            bin_obj = Bin(
                user=user, name=name, description=description, location=location, length=length, width=width, height=height, qr_code=qr_code_file
            )
            bin_obj.save()

            self.stdout.write(self.style.SUCCESS(f"Created Bin:\n\n{bin_obj.name}\n\n{bin_obj.description}\n\nLocation: {bin_obj.location}"))
