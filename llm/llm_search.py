from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from core.models import Bin, Item
from llm.llm_call import LLMCall
from llm.llm_handler import LangChainHandler


class ItemLocation(BaseModel):
    """Model for the response from the LLM describing item locations."""
    item_name: str
    bin_name: str
    confidence: str  # High, Medium, Low
    additional_info: str = ""


def find_item_location(query: str, user_id: int) -> str:
    """Find the location of an item using LLM.

    Args:
        query: The user's query about where an item might be
        user_id: The ID of the user making the query

    Returns:
        str: The formatted response from the LLM
    """
    # First, get all the user's items and bins
    user_bins = Bin.objects.filter(user_id=user_id)

    # Create bin context with items
    bins_context = []
    for storage_bin in user_bins:
        items = Item.objects.filter(bin=storage_bin)
        item_names = [item.name for item in items]
        bin_info = {
            "bin_name": storage_bin.name,
            "bin_location": storage_bin.location or "Unknown location",
            "items": item_names
        }
        bins_context.append(bin_info)

    # Format the context for the LLM
    formatted_context = ""
    for i, bin_info in enumerate(bins_context, 1):
        formatted_context += f"Bin #{i}: {bin_info['bin_name']} (located at: {bin_info['bin_location']})\n"
        formatted_context += "Contains items: " + ", ".join(bin_info["items"]) if bin_info["items"] else "Contains no items"
        formatted_context += "\n\n"

    # Get the path to the LLMCall JSON file
    base_dir = Path(__file__).resolve().parent
    llm_call_path = base_dir / ".." / "core" / "llm_calls" / "item_location_search.json"

    # Create the LLMCall instance using the from_json method
    llm_call = LLMCall.from_json(llm_call_path)

    # Create the handler and make the query
    handler = LangChainHandler(llm_call)
    return handler.query(query=query, formatted_context=formatted_context)
