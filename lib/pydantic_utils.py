from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic import BaseModel


def serialize_schema(schema: type[BaseModel]) -> dict[str, Any]:
    """Convert Pydantic model class to a serializable representation."""
    # Extract field information
    fields_info = {}
    for field_name, field_info in schema.model_fields.items():
        fields_info[field_name] = {
            "type": str(field_info.annotation),
            "required": field_info.is_required(),
            "description": field_info.description,
            "default": None if field_info.default is Ellipsis else str(field_info.default)
        }

    return {
        "class_name": schema.__name__,
        "module": schema.__module__,
        "fields": fields_info,
    }
