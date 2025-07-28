
from __future__ import annotations

# Standard library imports
import base64
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

# Third-party imports
import pillow_heif
from django.core.files.base import ContentFile
from PIL import Image as PILImage
from schemas.item_generation import GeneratedItem

# Register HEIF/HEIC opener for Pillow
pillow_heif.register_heif_opener()

# Local application imports
from core.models import Item, Bin
from llm.llm_call import LLMCall
from llm.llm_handler import StructuredLangChainHandler




def get_item_from_img(image_file: BinaryIO, bin_obj: Bin) -> Item:
    """Generate item name and description from an image using LLM and create the Item.

    Args:
        image_file (BinaryIO): A file-like object containing the image.
        bin_obj (Bin): The Bin instance the item belongs to.

    Returns:
        Item: The newly created Item instance.
    """
    # Resize image to limit size and encode to base64
    # Resize image to limit size and encode to base64
    # Ensure file pointer is at start
    image_file.seek(0)
    img = PILImage.open(image_file)
    img = img.convert("RGB")
    img.thumbnail((512, 512))
    buffer = BytesIO()
    img.save(buffer, format="JPEG")
    thumb_bytes = buffer.getvalue()
    buffer.close()
    image_data = base64.b64encode(thumb_bytes).decode("utf-8")

    # Load LLM call config for item generation
    json_path = Path(__file__).resolve().parent.parent / "core" / "llm_calls" / "item_image_generation.json"
    llm_call = LLMCall.from_json(str(json_path))

    # Initialize Structured handler with output schema
    handler = StructuredLangChainHandler(llm_call=llm_call, output_schema=GeneratedItem)

    # Query LLM with image data
    result: GeneratedItem = handler.query(image_data=image_data)

    # Create new Item instance
    item = Item(
        name=result.name,
        description=result.description,
        bin=bin_obj
    )

    # Save image to item.image
    image_name = getattr(image_file, "name", "uploaded_image")
    content_file = ContentFile(base64.b64decode(image_data), name=image_name)
    item.image = content_file

    # Save item to DB
    item.save()
    return item
