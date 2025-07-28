---
applyTo: "llm/llm_search.py,core/llm_calls/item_candidates_search.json,core/llm_calls/item_location_search.json,core/views.py,core/templates/core/item_search.html"
description: "Instructions for Item Search Functionality"
---
Item Search is the process by which a user can find specific items within their storage units using natural language queries (such as "where is my red jacket?").

It curently works in a two-step process:
1. **Item Candidates Search**: Given the user's query and text-based features of the user's entire Item collection, this step identifies a set of candidate items that are relevant to the query. If this step generates a single high-confidence candidate, it can directly return the location of that item.
2. **Item Location Search**: Given a set of ambiguous candidate items, this step uses a more resource-intensive search to confidently select a single candidate item and return its location.

Steps 1 and 2 are implemented in the `llm_search.py` file, with the LLM calls defined in the JSON files located in `core/llm_calls/`.

Both steps 1 and 2 use LLM's to perform the search. Step 2 accepts image inputs, while step 1 does not. 

WMS is in POC development stage. Post-POC enhancement will include search optimizations to make it more efficient and cost-effective. This might include a shift to embedding-search for the candidate-generation step. 