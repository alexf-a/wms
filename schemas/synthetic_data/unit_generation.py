"""Pydantic schema for unit generation in a single structured output."""

from pydantic import BaseModel, Field


class UnitGenerationOutput(BaseModel):
    """Schema for unit generation output including name, description, and location."""

    name: str = Field(
        description="The generated storage unit name, should be short, simple and realistic, maximum 30 characters"
    )
    description: str = Field(
        description="Descriptive phrase that includes both the purpose/context and specific item types, maximum 50 characters"
    )
    location: str = Field(
        description="Realistic household location name (e.g., 'Garage', 'Kitchen', 'Basement'), maximum 20 characters"
    )
