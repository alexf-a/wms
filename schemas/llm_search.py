"""Pydantic schema for LLM search operations."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ItemLocation(BaseModel):
    """Model for the response from the LLM describing item locations."""
    item_name: str
    unit_name: str
    confidence: str  # High, Medium, Low
    additional_info: str = Field(..., description="Any helpful additional information about the item location, or your reasoning for the confidence level.")

    def __str__(self) -> str:
        """Return a string representation of the item location."""
        return f"Item: {self.item_name}\nUnit: {self.unit_name}\nConfidence: {self.confidence}\nAdditional Info: {self.additional_info}"


class ItemSearchCandidate(BaseModel):
    """Model representing a candidate item match for search, with confidence score."""
    name: str = Field(..., description="Item name")
    unit_name: str = Field(..., description="Unit name")
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
        unit_name: The name of the unit containing the item
        image: Base64 encoded image data (optional)
    """
    name: str
    description: str
    unit_name: str
    image: str | None = None

    def to_prompt(self, exclude_fields: None | list[str] = None) -> str:
        """Format this ItemSearchInput for prompt insertion as a JSON string, optionally excluding fields by property name."""
        exclude_fields = set(exclude_fields or [])
        data = self.model_dump(exclude=exclude_fields)
        if "image" not in exclude_fields and data.get("image") is not None:
            data["image"] = "[Image provided below]"
        # Create a new ItemSearchInput instance with modified data
        prompt_model = ItemSearchInput(**data)
        # Return JSON string from the new instance, excluding original excluded fields
        return prompt_model.model_dump_json(exclude=exclude_fields)
