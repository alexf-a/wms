"""Context processors for WMS templates.

Provides additional context variables to all templates.
"""
from typing import Any

from django.conf import settings
from django.http import HttpRequest

from .models import (
    CATEGORY_2_UNITS,
    ITEM_QUANTITY_DECIMAL_PLACES,
    ITEM_QUANTITY_NON_COUNT_STEP,
    UNIT_2_NAME,
)


def registration_settings(request: HttpRequest) -> dict[str, Any]:
    """Add REGISTRATION_ENABLED setting to template context.

    Args:
        request: The HTTP request object.

    Returns:
        Dictionary with REGISTRATION_ENABLED setting.
    """
    return {
        "REGISTRATION_ENABLED": settings.REGISTRATION_ENABLED,
    }


def quantity_unit_options(request: HttpRequest) -> dict[str, Any]:
    """Add quantity unit options to template context for dynamic form rendering.

    Provides a flat list of quantity units with their categories for use in
    templates that need to render quantity unit dropdowns with data-category
    attributes for JavaScript filtering.

    Args:
        request: The HTTP request object.

    Returns:
        Dictionary with:
            - QUANTITY_UNIT_OPTIONS: List of dicts with value, label, category keys
            - QUANTITY_CATEGORIES: List of category names for radio buttons
            - QUANTITY_DECIMAL_PLACES: Number of decimal places for non-count quantities
            - QUANTITY_NON_COUNT_STEP: Increment/decrement step for non-count quantities
    """
    # Build flat list of units with category info
    options: list[dict[str, str]] = [
        {
            "value": unit,
            "label": UNIT_2_NAME[unit],
            "category": category,
        }
        for category, units in CATEGORY_2_UNITS.items()
        for unit in units
    ]

    # Categories for radio buttons
    categories: list[str] = list(CATEGORY_2_UNITS.keys())

    return {
        "QUANTITY_UNIT_OPTIONS": options,
        "QUANTITY_CATEGORIES": categories,
        "QUANTITY_DECIMAL_PLACES": ITEM_QUANTITY_DECIMAL_PLACES,
        "QUANTITY_NON_COUNT_STEP": float(ITEM_QUANTITY_NON_COUNT_STEP),
    }
