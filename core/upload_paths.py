"""Custom upload path functions for user-specific S3 directory structure."""
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Item

# Maximum length for filename stem to prevent excessively long paths
MAX_FILENAME_LENGTH = 50


def user_item_image_upload_path(instance: "Item", filename: str) -> str:
    """Generate upload path for item images specific to the unit owner.

    Path: users/{user_id}/item_images/{uuid}_{filename}

    For shared units, we still use the original owner's directory
    to maintain consistency and avoid duplication.
    
    Includes a UUID prefix to prevent filename collisions when multiple
    items are uploaded with the same filename (e.g., "image.jpg").
    """
    # Generate a unique prefix to prevent collisions
    unique_id = uuid.uuid4().hex[:8]
    
    # Preserve the original file extension
    ext = Path(filename).suffix
    safe_name = Path(filename).stem[:MAX_FILENAME_LENGTH]
    unique_filename = f"{unique_id}_{safe_name}{ext}"
    
    return f"users/{instance.unit.user.id}/item_images/{unique_filename}"
