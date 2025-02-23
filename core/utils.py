import qrcode
from qrcode.image.pil import PilImage

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
