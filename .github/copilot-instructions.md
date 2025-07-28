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
- `core/*`: Core Django functionality, data models, migrations and scripts/artifacts for management commands
- `core/llm_calls/*`: JSON files that define LLM calls, including system prompts, human prompts, and other parameters for LLM queries
- `aws_utils/*`: Utilities for interacting with AWS through boto3
- `llm/*`: LLM functionality.
- `schemas/*`: Data-schemas (represented as Pydantic Models) for different kinds of data, including synthetic data generating. 

## Development Guidelines
- **Django Core**: Follow Django best practices for models, views, and forms.
- **LLM Functionality**: Use the LLMHandler for all LLM queries, and ensure that LLMCall objects are used to encapsulate query parameters.
- **Ruff**: Use Ruff for linting and code quality checks. Follow the project's linting rules and fix any issues reported by Ruff.
- **Google Docstrings**: Use Google-style docstrings for all public methods and classes.
- **Testing**: All tests are written using pytest. Use the `test_*.py` naming convention for test files and organize tests in the `tests/` directory. Ensure that all new features and bug fixes are covered by tests.

