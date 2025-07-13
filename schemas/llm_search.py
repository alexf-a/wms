"""Pydantic schema for LLM search operations."""

from __future__ import annotations

from pydantic import BaseModel, Field, TypeAdapter


class ItemLocation(BaseModel):
    """Model for the response from the LLM describing item locations."""
    item_name: str
    bin_name: str
    confidence: str  # High, Medium, Low
    additional_info: str = ""

    def __str__(self) -> str:
        """Return a string representation of the item location."""
        return f"Item: {self.item_name}\nBin: {self.bin_name}\nConfidence: {self.confidence}\nAdditional Info: {self.additional_info}"


class ItemSearchCandidate(BaseModel):
    """Model representing a candidate item match for search, with confidence score."""
    name: str = Field(..., description="Item name")
    bin_name: str = Field(..., description="Bin name")
    confidence: float = Field(
        ..., description="Confidence score between 0 and 1 (inclusive)", ge=0.0, le=1.0
    )

class ItemSearchCandidates(BaseModel):
    """Model representing a list of item search candidates."""
    candidates: list[ItemSearchCandidate] = Field(
        default_factory=list, description="List of item search candidates"
    )

    def __str__(self) -> str:
        """Return a string representation of the item search candidates."""
        return "\n".join(
            [candidate.model_dump_json() for candidate in self.candidates]
        )


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
        data = self.model_dump(exclude=exclude_fields)
        if "image" not in exclude_fields and data.get("image") is not None:
            data["image"] = "[Image provided below]"
        return TypeAdapter(type(self)).dump_json(data).decode()
