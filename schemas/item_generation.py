from pydantic import BaseModel, Field


class GeneratedItem(BaseModel):
    """Pydantic model representing generated item attributes from an image.

    Attributes:
        name (str): Generated name of the item.
        description (str): Generated description of the item.
    """
    name: str = Field(..., max_length=30, description="The name of the item generated from the image.")
    description: str = Field(..., max_length=200, description="The description of the item generated from the image.")
