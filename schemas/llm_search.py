"""Pydantic schema for LLM search operations."""

from pydantic import BaseModel


class ItemLocation(BaseModel):
    """Model for the response from the LLM describing item locations."""
    item_name: str
    bin_name: str
    confidence: str  # High, Medium, Low
    additional_info: str = ""

    def __str__(self) -> str:
        """Return a string representation of the item location."""
        return f"Item: {self.item_name}\nBin: {self.bin_name}\nConfidence: {self.confidence}\nAdditional Info: {self.additional_info}"