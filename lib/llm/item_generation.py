
from __future__ import annotations

# Standard library imports
import base64
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

# Third-party imports
import pillow_heif
from django.core.files.base import ContentFile
from PIL import Image as PILImage

# Local application imports
from core.models import Bin, Item
from lib.llm.llm_handler import StructuredLangChainHandler
from lib.llm.utils import get_llm_call
from schemas.item_generation import GeneratedItem

# Register HEIF/HEIC opener for Pillow
pillow_heif.register_heif_opener()


@lru_cache(maxsize=1)
def _get_cached_handler() -> StructuredLangChainHandler:
    """Get a cached StructuredLangChainHandler for item generation.

    Returns:
        StructuredLangChainHandler: Cached handler instance.
    """
    llm_call = get_llm_call("item_generation/item_image_generation")
    return StructuredLangChainHandler(llm_call=llm_call, output_schema=GeneratedItem)




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

    # Get cached handler and query with image
    handler = _get_cached_handler()
    result: GeneratedItem = handler.query_with_image(image_data)

    # Create new Item instance
    item = Item(
        name=result.name,
        description=result.description,
        bin=bin_obj
    )

    # Save image to item.image
    image_name = getattr(image_file, "name", "uploaded_image")
    # Extract just the filename to avoid path traversal issues
    if image_name != "uploaded_image":
        image_name = Path(image_name).name
    content_file = ContentFile(base64.b64decode(image_data), name=image_name)
    item.image = content_file

    # Save item to DB
    item.save()
    return item
