from __future__ import annotations

from pathlib import Path
from typing import cast

from core.models import Bin, Item
from llm.llm_call import LLMCall
from llm.llm_handler import StructuredLangChainHandler
from schemas.llm_search import ItemLocation, ItemSearchCandidates

#TODO: Initialize LLMCall as global variable to avoid reloading it every time

# Search algo improvement ideas:
# - Impractical to stuff all items into the prompt, so we need to use a more efficient search algorithm
# - Use vector embeddings to find similar items based on the query

def perform_candidate_search(user_query: str, user_id: int, k: int = 10) -> list[ItemSearchCandidates]:
    """Perform a search for item candidates using a Large Language Model (LLM).

    This function retrieves all items associated with a given user, formats them
    into a context string, and then uses a pre-configured LLM call to identify
    the most relevant items based on the user's query.

    Args:
        user_query (str): The query from the user describing the item to search for.
        user_id (int): The ID of the user whose items to search.
        k (int, optional): The maximum number of candidates to return. Defaults to 10.

    Returns:
        list[ItemSearchCandidates]: A list of candidate items returned by the LLM,
            matching the search query.
    """
    items = Item.objects.filter(user_id=user_id)
    prompt_ctxt = str([item.to_search_input().to_prompt() for item in items])

    # Get the path to the candidate search LLMCall JSON file
    base_dir = Path(__file__).resolve().parent
    candidates_llm_call_path = base_dir / ".." / "core" / "llm_calls" / "item_candidates_search.json"

    # Create the LLMCall instance for candidate generation
    candidates_llm_call = LLMCall.from_json(candidates_llm_call_path)
    candidates_handler = StructuredLangChainHandler(llm_call=candidates_llm_call, output_schema=ItemSearchCandidates)
    results = candidates_handler.query(user_query=user_query, formatted_context=prompt_ctxt, k=k)
    # Query for item candidates
    return cast("ItemSearchCandidates", results)

def get_item_location(candidates: list[ItemSearchCandidates]) -> ItemLocation:
    """Extract the item location from the candidates."""
    pass


def find_item_location(user_query: str, user_id: int, k: int = 10) -> ItemLocation:
    """Find the location of an item using LLM.

    Args:
        user_query: The user's query about where an item might be
        user_id: The ID of the user making the query
        k: The number of candidates to return (default 10)

    Returns:
        str: The formatted response from the LLM
    """
    candidates = perform_candidate_search(user_query, user_id, k)

    # ...existing code for follow-up (e.g., image-based disambiguation or returning ItemLocation)...
    # For now, just return the candidates_result for demonstration
    return get_item_location(candidates)