"""Pydantic schemas for bin generation LLM outputs."""

from pydantic import BaseModel, Field


class BinNameOutput(BaseModel):
    """Schema for bin name generation output."""
    
    bin_name: str = Field(
        description="The generated storage bin name, should be short, simple and realistic"
    )
    reasoning: str = Field(
        description="Brief explanation of why this name was chosen and how it relates to the purpose/contents"
    )


class BinDescriptionOutput(BaseModel):
    """Schema for bin description generation output."""
    
    description: str = Field(
        description="Concise and informative description of the storage bin's purpose or contents"
    )
    reasoning: str = Field(
        description="Brief explanation of how the description fits the bin name and intended use"
    )


class BinLocationOutput(BaseModel):
    """Schema for bin location generation output."""
    
    location: str = Field(
        description="Realistic household location name (e.g., 'Living Room', 'Kitchen', 'Garage'), three words maximum"
    )
    reasoning: str = Field(
        description="Brief explanation of why this location is appropriate for the bin and its contents"
    )
