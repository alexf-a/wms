from abc import ABC, ABCMeta
from enum import Enum, EnumMeta


# Create a compatible metaclass that inherits from both EnumMeta and ABCMeta
class EnumABCMeta(EnumMeta, ABCMeta):
    """A metaclass that combines EnumMeta and ABCMeta."""

class ModelID(ABC, Enum, metaclass=EnumABCMeta):
    """Enumeration of available models."""
