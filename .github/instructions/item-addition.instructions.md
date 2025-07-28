---
applyTo: "core/llm_calls/item_generation.json,core/views.py,llm/item_generation.py,core/templates/core/auto_generate_item.html,core/templates/core/confirm_item.html"
description: "Instructions for Item Addition Functionality"
---

## User Story
As a user, I want to add items to my storage units so that I can keep track of my belongings.

I want this process to be simple and intuitive, allowing me to quickly input details about the items I am storing.

I want to minimize manual data entry by using features like barcode scanning, image recognition, and natural language processing.

## Implementation Overview

The Item Addition process will prompt the user to upload an image, and generate the text-based features of the item using an LLM. The user will then be able to review and edit these features before confirming the addition of the item.

## User Flow
1. User clicks "Add Items to Bin"
2. User is prompted to select a bin for the new item
    - If no bins exist, user is directed to create a bin first
    - If bins exist, user selects one from a dropdown list
3. User sees options: "Upload Image" or "Manual Entry"
4. If "Upload Image":
    1. User uploads image and selects bin
    2. Loading indicator while processing
    3. Redirect to confirmation page with auto-generated features + image preview
    4. User reviews/edits the generated name and description
    5. User confirms or goes back to retry
5. Success message and option to add another item or return to home