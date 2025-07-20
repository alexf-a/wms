from __future__ import annotations

from pathlib import Path
from typing import cast

from core.models import Item
from llm.llm_call import LLMCall
from llm.llm_handler import StructuredLangChainHandler
from schemas.llm_search import ItemLocation, ItemSearchCandidates

#TODO: Initialize LLMCall as global variable to avoid reloading it every time

#TODO: Replace perform_candidate_search with a more efficient search algorithm

# High confidence threshold for single candidate acceptance
HIGH_CONFIDENCE_THRESHOLD = 0.8

def get_item_search_context(items: list[Item]) -> str:
    """Generate a context string for LLM search from a list of Item instances."""
    return str([item.to_search_input().to_prompt() for item in items])

def perform_candidate_search(user_query: str, user_id: int, k: int = 10) -> ItemSearchCandidates:
    """Perform a search for item candidates using a Large Language Model (LLM).

    This function retrieves all items associated with a given user, formats them
    into a context string, and then uses a pre-configured LLM call to identify
    the most relevant items based on the user's query.

    Args:
        user_query (str): The query from the user describing the item to search for.
        user_id (int): The ID of the user whose items to search.
        k (int, optional): The maximum number of candidates to return. Defaults to 10.

    Returns:
        ItemSearchCandidates: A list of candidate items returned by the LLM,
            matching the search query.
    """
    items = Item.objects.filter(bin__user_id=user_id)
    prompt_ctxt = get_item_search_context(items)

    # Get the path to the candidate search LLMCall JSON file
    base_dir = Path(__file__).resolve().parent
    candidates_llm_call_path = base_dir / ".." / "core" / "llm_calls" / "item_candidates_search.json"

    # Create the LLMCall instance for candidate generation
    candidates_llm_call = LLMCall.from_json(candidates_llm_call_path)
    candidates_handler = StructuredLangChainHandler(llm_call=candidates_llm_call, output_schema=ItemSearchCandidates)
    results: ItemSearchCandidates = candidates_handler.query(user_query=user_query, formatted_context=prompt_ctxt, k=k)
    # Query for item candidates
    return cast("ItemSearchCandidates", results)

def get_item_location(candidates: ItemSearchCandidates, user_id: int, user_query: str) -> ItemLocation:
    """Extract the item location from the candidates."""
    # If and only if there is a single ItemSearchCandidate with a high confidence score, create an ItemLocation from the candidate and return it.
    # Collect all candidates with high confidence scores across all candidate groups
    high_confidence_candidates = [
        candidate
        for candidate in candidates.candidates
        if candidate.confidence >= HIGH_CONFIDENCE_THRESHOLD
    ]

    # Return early only if there's exactly one high confidence candidate
    if len(high_confidence_candidates) == 1:
        candidate = high_confidence_candidates[0]
        return ItemLocation(
            item_name=candidate.name,
            bin_name=candidate.bin_name,
            confidence="High",
            additional_info=f"Found with confidence score: {candidate.confidence}"
        )

    # Otherwise, use the LLMCall JSON at core/llm_calls/item_location_search.json to make a follow-up query to the LLM to disambiguate the candidates.
    # The follow-up query should return an ItemLocation object.
    
    # Prepare context from all candidates by retrieving the relevant Items from the DB
    candidate_item_names = [candidate.name for candidate in candidates.candidates]
    relevant_items = Item.objects.filter(name__in=candidate_item_names, bin__user_id=user_id)
    formatted_context = get_item_search_context(relevant_items)

    # Get the path to the location search LLMCall JSON file
    base_dir = Path(__file__).resolve().parent
    location_llm_call_path = base_dir / ".." / "core" / "llm_calls" / "item_location_search.json"

    # Create the LLMCall instance for location disambiguation
    location_llm_call = LLMCall.from_json(location_llm_call_path)
    location_handler = StructuredLangChainHandler(llm_call=location_llm_call, output_schema=ItemLocation)

    result = location_handler.query(query=user_query, formatted_context=formatted_context)
    return cast("ItemLocation", result)


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
    return get_item_location(candidates, user_id, user_query)
