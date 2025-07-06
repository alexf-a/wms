from __future__ import annotations

from pathlib import Path
from typing import cast

from core.models import Bin, Item
from llm.llm_call import LLMCall
from llm.llm_handler import StructuredLangChainHandler
from schemas.llm_search import ItemLocation


def find_item_location(query: str, user_id: int) -> ItemLocation:
    """Find the location of an item using LLM.

    Args:
        query: The user's query about where an item might be
        user_id: The ID of the user making the query

    Returns:
        str: The formatted response from the LLM
    """
    # First, get all the user's items and bins
    user_bins = Bin.objects.filter(user_id=user_id)

    # Create bin context with items and collect ItemSearchInput objects
    bins_context = []
    items_with_images = []  # Store ItemSearchInput objects for multimodal input

    for storage_bin in user_bins:
        items = Item.objects.filter(bin=storage_bin)
        item_details = []
        for item in items:
            # Convert item to search input format
            item_search_input = item.to_search_input()
            
            # Add to our collection if it has an image
            if item_search_input.image is not None:
                items_with_images.append(item_search_input)
            
            # Create item info for context formatting
            item_info = {
                "name": item_search_input.name,
                "description": item_search_input.description,
                "has_image": item_search_input.image is not None
            }
            item_details.append(item_info)

        bin_info = {
            "bin_name": storage_bin.name,
            "bin_location": storage_bin.location or "Unknown location",
            "items": item_details
        }
        bins_context.append(bin_info)

    # Format the context for the LLM
    formatted_context = ""
    for i, bin_info in enumerate(bins_context, 1):
        formatted_context += f"Bin #{i}: {bin_info['bin_name']} (located at: {bin_info['bin_location']})\n"
        if bin_info["items"]:
            formatted_context += "Contains items:\n"
            for item in bin_info["items"]:
                formatted_context += f"  - {item['name']}: {item['description']}"
                if item["has_image"]:
                    formatted_context += " [Image provided below]"
                formatted_context += "\n"
        else:
            formatted_context += "Contains no items"
        formatted_context += "\n\n"

    # Get the path to the LLMCall JSON file
    base_dir = Path(__file__).resolve().parent
    llm_call_path = base_dir / ".." / "core" / "llm_calls" / "item_location_search.json"

    # Create the LLMCall instance using the from_json method
    llm_call = LLMCall.from_json(llm_call_path)

    # Create the handler and make the query with multimodal content
    handler = StructuredLangChainHandler(llm_call=llm_call, output_schema=ItemLocation)

    # If we have items with images, add them as multimodal messages
    if items_with_images:
        # Build multimodal human message content
        content_parts = []

        # Add each image with context
        for item in items_with_images:
            # Add text context for the image
            image_context = f"\nImage of '{item.name}' from bin '{item.bin_name}':"
            content_parts.append({"type": "text", "text": image_context})

            # Add the image
            content_parts.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": item.image
                }
            })

        # Add the multimodal message to the handler
        handler.add_message("user", content_parts)

    # Query with all template variables - the handler will manage additional messages
    return cast("ItemLocation", handler.query(query=query, formatted_context=formatted_context))
