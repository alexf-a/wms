import secrets
from io import BytesIO

import qrcode
from django.core.files.base import ContentFile
from qrcode.image.pil import PilImage


def generate_bin_access_token() -> str:
    """Generate a random, URL-safe access token for a bin."""
    return secrets.token_urlsafe(16)


def get_qr_code(data: str) -> PilImage:
    """Create a QR code containing the provided data string.

    Args:
        data: The string content to embed in the QR code.

    Returns:
        qrcode.image.pil.PilImage: The generated QR code image.
    """
    return qrcode.make(data)


def get_qr_code_file(data: str, *, filename: str) -> ContentFile:
    """Create a QR code file containing the provided data string.

    Args:
        data: The string content to embed in the QR code.
        filename: The desired filename for the QR code image.

    Returns:
        ContentFile: The generated QR code file ready for storage.
    """
    qr_code = get_qr_code(data)
    buffer = BytesIO()
    qr_code.save(buffer, format="PNG")
    buffer.seek(0)
    return ContentFile(buffer.read(), name=filename)
