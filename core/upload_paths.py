"""Custom upload path functions for user-specific S3 directory structure."""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Bin, Item


def user_qr_code_upload_path(instance: "Bin", filename: str) -> str:
    """Generate upload path for QR codes specific to the bin owner.

    Path: users/{user_id}/qr_codes/{filename}
    """
    return f"users/{instance.user.id}/qr_codes/{filename}"


def user_item_image_upload_path(instance: "Item", filename: str) -> str:
    """Generate upload path for item images specific to the bin owner.

    Path: users/{user_id}/item_images/{filename}

    For shared bins, we still use the original owner's directory
    to maintain consistency and avoid duplication.
    """
    return f"users/{instance.bin.user.id}/item_images/{filename}"
