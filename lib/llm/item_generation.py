
from __future__ import annotations

# Standard library imports
import base64
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

# Third-party imports
import pillow_heif
from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image as PILImage

# Local application imports
from aws_utils.region import AWSRegion
from core.models import Unit, Item
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
    # Get the region from Django settings, defaulting to US_WEST_2
    region_name = settings.AWS_BEDROCK_REGION_NAME
    region = AWSRegion(region_name)
    return StructuredLangChainHandler(llm_call=llm_call, output_schema=GeneratedItem, region=region)

def get_img_str(img_file: BinaryIO) -> str:
    """Create a JPEG thumbnail from an image file and return it as a base64 string.

    The image is converted to RGB, resized to fit within 512x512 pixels while
    preserving aspect ratio, encoded as JPEG, and then base64-encoded.

    Args:
        img_file (BinaryIO): A file-like object containing the image.

    Returns:
        str: Base64-encoded JPEG thumbnail.
    """
    # Resize image to limit size and encode to base64
    img_file.seek(0)
    img = PILImage.open(img_file)
    img = img.convert("RGB")
    img.thumbnail((512, 512))
    buffer = BytesIO()
    img.save(buffer, format="JPEG")
    thumb_bytes = buffer.getvalue()
    buffer.close()
    return base64.b64encode(thumb_bytes).decode("utf-8")

def extract_item_features_from_image(img_file: BinaryIO) -> GeneratedItem:
    """Extract structured item features from an image file using the LLM handler.

    The image is converted into a base64-encoded JPEG thumbnail, sent to the
    cached StructuredLangChainHandler, and the resulting GeneratedItem schema
    is returned.

    Args:
        img_file (BinaryIO): A file-like object containing the image.

    Returns:
        GeneratedItem: Parsed/generated item features inferred from the image.
    """
    img_str = get_img_str(img_file)
    # Get cached handler and extract features
    handler = _get_cached_handler()
    result: GeneratedItem = handler.query_with_image(img_str)
    return result
