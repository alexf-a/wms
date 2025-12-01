---
applyTo: "core/llm_calls/item_generation.json,core/views.py,llm/item_generation.py,core/templates/core/auto_generate_item.html,core/templates/core/confirm_item.html,core/templates/core/add_items_to_bin.html"
description: "Instructions for Item Addition Functionality"
---

## User Story
As a user, I want to add items to my storage units so that I can keep track of my belongings.

I want this process to be simple and intuitive, allowing me to quickly input details about the items I am storing.

I want to minimize manual data entry by using features like barcode scanning, image recognition, and natural language processing.

## Implementation Overview

The Item Addition process will prompt the user to upload an image, and generate the text-based features of the item using an LLM. The user will then be able to review and edit these features before confirming the addition of the item.