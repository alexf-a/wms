import qrcode
from qrcode.image.pil import PilImage
from io import BytesIO
from django.core.files.base import ContentFile

#TODO: Must include user information in the QR code data, to ensure uniqueness
def get_qr_code(  # noqa: PLR0913
    name: str,
    description: str,
    location: str,
    length: float,
    width: float,
    height: float,
) -> PilImage:
    """Create a QR code with the given details.

    Args:
        name (str): The name.
        description (str): The description.
        location (str): The location.
        length (float): The length.
        width (float): The width.
        height (float): The height.

    Returns:
        qrcode.image.pil.PilImage: The generated QR code image.
    """
    data = (
        f"Name: {name}, Description: {description}, Location: {location}, "
        f"Dimensions: {length}x{width}x{height}"
    )
    return qrcode.make(data)

def get_qr_code_file(  # noqa: PLR0913
    name: str,
    description: str,
    location: str,
    length: float,
    width: float,
    height: float,
) -> ContentFile:
    """Create a QR code file with the given details.

    Args:
        name (str): The name.
        description (str): The description.
        location (str): The location.
        length (float): The length.
        width (float): The width.
        height (float): The height.

    Returns:
        ContentFile: The generated QR code file.
    """
    qr_code = get_qr_code(name, description, location, length, width, height)
    buffer = BytesIO()
    qr_code.save(buffer, format="PNG")
    buffer.seek(0)
    return ContentFile(buffer.read(), name=f"{name}_qr.png")
