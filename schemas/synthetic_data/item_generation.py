"""Pydantic schema for item generation in a single structured output."""

from pydantic import BaseModel, Field


class ItemGenerationOutput(BaseModel):
    """Schema for item generation output including name and description."""

    name: str = Field(
        description="Realistic item name that would logically belong in the specified storage bin, maximum 30 characters"
    )
    description: str = Field(
        description="Realistic, detailed description including relevant details like condition, size, color, "
                   "material, or usage notes, maximum 200 characters"
    )
