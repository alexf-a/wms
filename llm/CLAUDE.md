# LLM Infrastructure

## Overview

All LLM functionality uses a centralized handler pattern with declarative call definitions.

## Key Components

- **LLMCall** — A convenience class encapsulating all arguments for an LLM query (model, prompts, parameters)
- **LLMHandler** — A wrapper class providing a common interface for querying different LLM APIs. All LLM queries must go through this handler.
- **Claude4XMLFunctionCallParser** — Custom output parser for Claude 4's XML-style function calling format, created as a workaround for the lack of structured output support in LangChain < 0.3.27 for Claude 4 models. See: https://github.com/langchain-ai/langchain-aws/issues/521#issuecomment-3047492505

## LLM Call Definitions

LLM calls are defined declaratively as JSON files in `core/llm_calls/`:

- `item_generation.json` — Prompts for generating item text features from images
- `item_candidates_search.json` — Prompts for text-based item candidate search
- `item_location_search.json` — Prompts for image-aware item location disambiguation

## Modules

- `llm/item_generation.py` — Item feature extraction from images (used during item addition)
- `llm/llm_search.py` — Two-step item search (candidate generation → location disambiguation)
