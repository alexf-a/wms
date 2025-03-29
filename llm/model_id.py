from abc import ABC, ABCMeta
from enum import Enum


# Create a compatible metaclass that inherits from both EnumMeta and ABCMeta
class EnumABCMeta(type(Enum), ABCMeta):
    """A metaclass that combines EnumMeta and ABCMeta."""

class ModelID(Enum, ABC):
    """Enumeration of available models."""
