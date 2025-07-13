from __future__ import annotations

from pathlib import Path
from typing import cast

from core.models import Bin, Item
from llm.llm_call import LLMCall
from llm.llm_handler import StructuredLangChainHandler
from schemas.llm_search import ItemLocation

# Search algo improvement ideas:
# - Impractical to stuff all items into the prompt, so we need to use a more efficient search algorithm
# - Use vector embeddings to find similar items based on the query


def find_item_location(query: str, user_id: int) -> ItemLocation:
    """Find the location of an item using LLM.

    Args:
        query: The user's query about where an item might be
        user_id: The ID of the user making the query

    Returns:
        str: The formatted response from the LLM
    """
    # Get all the user's bins
    user_bins = Bin.objects.filter(user_id=user_id)

    # Use Bin.to_search_prompt to build the context
    formatted_context = "".join([bin_.to_search_prompt() for bin_ in user_bins])

    # Get the path to the LLMCall JSON file
    base_dir = Path(__file__).resolve().parent
    llm_call_path = base_dir / ".." / "core" / "llm_calls" / "item_location_search.json"

    # Create the LLMCall instance using the from_json method
    llm_call = LLMCall.from_json(llm_call_path)

    # Create the handler and make the query with multimodal content
    handler = StructuredLangChainHandler(llm_call=llm_call, output_schema=ItemLocation)

    # Query with all template variables - the handler will manage additional messages
    return cast("ItemLocation", handler.query(query=query, formatted_context=formatted_context))
