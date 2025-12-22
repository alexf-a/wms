"""Custom upload path functions for user-specific S3 directory structure."""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Item


def user_item_image_upload_path(instance: "Item", filename: str) -> str:
    """Generate upload path for item images specific to the unit owner.

    Path: users/{user_id}/item_images/{filename}

    For shared units, we still use the original owner's directory
    to maintain consistency and avoid duplication.
    """
    return f"users/{instance.unit.user.id}/item_images/{filename}"
