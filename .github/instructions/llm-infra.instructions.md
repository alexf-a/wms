---
applyTo: 'llm/**'
---

## LLM Infrastructure Overview
- LLMCall: A convenience class representing all arguments needed for an LLM query
- LLMHandler: A convenience wrapper-class and common-interface for querying different LLM API's
- Claude4XMLFunctionCallParser: A custom output parser for Claude 4's XML-style function calling format, created as a workaround for the lack of structured output support in LangChain < 0.3.27 for Claude 4 models. See https://github.com/langchain-ai/langchain-aws/issues/521#issuecomment-3047492505
- LLM-powered Item search logic
- LLM-powered logic to generate Item text features from images