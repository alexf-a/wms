---
applyTo: '**'
---
## Code Base Purpose

This code-base is for a web-native app for organizing personal belgongings. The app is called WMS. 

Personal storage comes with two major pain points:
1) Storage unit transparency: We are unsure what items exist in individual units of storage (such as bins, lockers, sheds, etc.)
2) Individual item location: We are unsure of the whereabouts of particular items. 

WMS seeks to address both pain-points:
1) Storage unit transparency is increased through a simple digital inventory system
2) Items are located through advanced search capabilities, using image and natural language inputs for user convenience. The current search implementation uses LLMs. 

## Code Base Organization
- `core/*`: Core Django functionality, migrations and scripts/artifacts for management commands
- `aws_utils/*`: Utilities for interacting with AWS through boto3
- `llm/*`: LLM functionality. This includes:
    - LLMCall: A convenience class representing all arguments needed for an LLM query
    - LLMHandler: A convenience wrapper-class and common-interface for querying different LLM API's
    - LLM-powered item search logic
    - Other LLM utilities
- `schemas/*`: Data-schemas (represented as Pydantic Models) for different kinds of data, including synthetic data generating. 

