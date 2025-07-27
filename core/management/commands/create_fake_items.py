from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import Bin, Item
from lib.llm.llm_handler import StructuredLangChainHandler
from lib.llm.claude4_xml_parser import Claude4XMLParsingError
from lib.llm.utils import get_llm_call
from schemas.synthetic_data.item_generation import ItemGenerationOutput
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import boto3
import base64
import json


class Command(BaseCommand):
    help = "Create fake items with realistic names for testing"

    def add_arguments(self, parser):
        parser.add_argument("count", type=int, help="Number of items to create per bin")
        parser.add_argument("--username", "-u", type=str, required=True, help="Username of the bin owner")
        parser.add_argument("--all-bins", "-a", action="store_true", help="Create items for all user's bins")
        parser.add_argument("--bin-name", "-b", type=str, help="Name of specific bin to populate")

    def handle(self, *args, **options):
        user_model = get_user_model()
        username = options.get("username")
        count = options["count"]
        bin_name = options.get("bin_name")
        all_bins = options.get("all_bins")

        try:
            user = user_model.objects.get(username=username)
        except user_model.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"User '{username}' not found."))
            return

        # Set up LLM for item generation
        item_llm_call = get_llm_call("synthetic_data/item_generation")
        
        item_handler = StructuredLangChainHandler(
            llm_call=item_llm_call,
            output_schema=ItemGenerationOutput
        )

        # Get bins to populate
        if bin_name:
            try:
                bins = [Bin.objects.get(user=user, name=bin_name)]
            except Bin.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Bin '{bin_name}' not found for user '{username}'."))
                return
        elif all_bins:
            bins = Bin.objects.filter(user=user)
            if not bins.exists():
                self.stdout.write(self.style.ERROR(f"No bins found for user '{username}'."))
                return
        else:
            bins = Bin.objects.filter(user=user).order_by("?")[:1]
            if not bins:
                self.stdout.write(self.style.ERROR(f"No bins found for user '{username}'."))
                return

        # Generate items for each bin
        for storage_bin in bins:
            self.stdout.write(self.style.SUCCESS(f"Creating {count} items for bin: {storage_bin.name}"))
            self.stdout.write(f"  Description: {storage_bin.description}")

            # Get existing item names for this bin to avoid duplicates
            existing_item_names = set(
                Item.objects.filter(bin=storage_bin).values_list("name", flat=True)
            )

            for i in range(count):
                # Generate complete item using LLM, ensuring uniqueness
                max_attempts = 10
                item_data = None
                for attempt in range(max_attempts):
                    # Create list of existing items for context
                    existing_items_str = ", ".join(existing_item_names) if existing_item_names else "None"
                    
                    try:
                        # Generate complete item using structured LLM
                        result = item_handler.query(
                            bin_name=storage_bin.name, 
                            bin_description=storage_bin.description,
                            existing_items=existing_items_str
                        )
                        candidate_name = result.name.strip().title()

                        # Check if name is unique (case-insensitive)
                        if candidate_name.lower() not in {name.lower() for name in existing_item_names}:
                            item_data = result
                            existing_item_names.add(candidate_name)
                            break

                        self.stdout.write(
                            self.style.WARNING(
                                f"Attempt {attempt + 1}: Generated duplicate name '{candidate_name}', retrying..."
                            )
                        )
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

                if item_data is None:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Failed to generate unique item after {max_attempts} attempts. Skipping this item."
                        )
                    )
                    continue

                # Clean up the item name and description
                item_name = "".join(char for char in item_data.name if char.isalpha() or char.isspace()).strip()
                description = item_data.description.strip()

                # Create the item
                item = Item(
                    name=item_name,
                    description=description,
                    bin=storage_bin
                )

                # Generate image via AWS Bedrock using text-to-image
                image_success = False
                try:
                    client = boto3.client("bedrock-runtime")
                    body = {
                        "prompt": f"Generate an image of {item_name}",
                        "mode": "text-to-image",
                        "aspect_ratio": "1:1",
                        "output_format": "jpeg"
                    }
                    response = client.invoke_model(
                        modelId="stability.sd3-5-large-v1:0",
                        contentType="application/json",
                        accept="application/json",
                        body=json.dumps(body)
                    )
                    result = json.loads(response['body'].read().decode('utf-8'))
                    if "images" in result and result["images"]:
                        img_b64 = result["images"][0]
                        img_data = base64.b64decode(img_b64)
                        
                        # Load the image and resize it to half size
                        img = Image.open(BytesIO(img_data))
                        original_width, original_height = img.size
                        new_width = original_width // 2
                        new_height = original_height // 2
                        img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        
                        # Save the resized image
                        output = BytesIO()
                        img_resized.save(output, format="JPEG", quality=90)
                        output.seek(0)
                        
                        file_name = f"{item_name.replace(' ', '_')}.jpg"
                        item.image.save(file_name, ContentFile(output.read()), save=False)
                        image_success = True
                    else:
                        raise ValueError("No images returned from Bedrock.")
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"Failed to generate image via Bedrock for {item_name}: {str(e)}"))

                # If Bedrock failed, generate a simple placeholder image with item name
                if not image_success:
                    try:
                        width, height = 200, 150
                        img = Image.new("RGB", (width, height), color=(240, 240, 240))
                        draw = ImageDraw.Draw(img)

                        # Add text
                        text_color = (60, 60, 60)
                        font_size = min(12, int(150 / (len(item_name) / 8)))

                        try:
                            font = ImageFont.truetype("Arial", font_size)
                        except OSError:
                            font = ImageFont.load_default()

                        # Draw item name in center
                        text_bbox = draw.textbbox((0, 0), item_name, font=font)
                        text_width = text_bbox[2] - text_bbox[0]
                        text_height = text_bbox[3] - text_bbox[1]
                        position = ((width - text_width) // 2, (height - text_height) // 2)
                        draw.text(position, item_name, fill=text_color, font=font)

                        # Save the image
                        output = BytesIO()
                        img.save(output, format="JPEG", quality=90)
                        output.seek(0)

                        file_name = f"{item_name.replace(' ', '_')}_placeholder.jpg"
                        item.image.save(file_name, ContentFile(output.read()), save=False)
                        image_success = True

                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f"Failed to generate placeholder image for {item_name}: {str(e)}")
                        )

                # Only save the item if we successfully created an image
                if image_success:
                    item.save()
                    self.stdout.write(self.style.SUCCESS(f"  Created Item: {item.name}"))
                else:
                    # Delete the item if we couldn't create any image
                    self.stdout.write(self.style.ERROR(f"Could not create any image for {item_name}. Item not created."))
                    continue
