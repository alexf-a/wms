from __future__ import annotations

from pydantic import BaseModel


class ItemSearchInput(BaseModel):
    """Pydantic model representing item data for LLM search input.
    
    Attributes:
        name: The name of the item
        description: The description of the item
        bin_name: The name of the bin containing the item
        image: Base64 encoded image data (optional)
    """
    name: str
    description: str
    bin_name: str
    image: str | None = None
