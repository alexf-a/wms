"""Utilities for LLM functionality."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings

from lib.llm.llm_call import LLMCall


def get_llm_call(filename: str) -> LLMCall:
    """Load an LLMCall from the configured LLM_CALLS_DIR.

    Args:
        filename: The name of the JSON file (with or without .json extension)
                 Can include subdirectory path like "item_search/item_candidates_search"

    Returns:
        LLMCall: The loaded LLM call configuration

    Raises:
        FileNotFoundError: If the LLM call file doesn't exist
    """
    if not filename.endswith(".json"):
        filename = f"{filename}.json"

    llm_calls_dir = Path(settings.LLM_CALLS_DIR)
    json_path = llm_calls_dir / filename

    if not json_path.exists():
        msg = f"LLM call file not found: {json_path}"
        raise FileNotFoundError(msg)

    return LLMCall.from_json(str(json_path))


def get_llm_calls_dir() -> Path:
    """Get the configured LLM calls directory path.

    Returns:
        Path: The path to the LLM calls directory
    """
    return Path(settings.LLM_CALLS_DIR)
