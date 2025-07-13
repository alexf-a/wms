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

    def to_prompt(self, exclude_fields: None | list[str] = None) -> str:
        """Format this ItemSearchInput for prompt insertion as a JSON string, optionally excluding fields by property name."""
        exclude_fields = set(exclude_fields or [])
        # Use Pydantic's dict() to exclude fields, then json() for serialization
        data = self.dict(exclude=exclude_fields)
        # If image is present and not excluded, replace its value with a marker
        if "image" not in exclude_fields and data.get("image") is not None:
            data["image"] = "[Image provided below]"
        from pydantic import TypeAdapter
        return TypeAdapter(type(self)).dump_json(data).decode()
