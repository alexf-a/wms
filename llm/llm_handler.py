from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from langchain.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
)
from langchain_aws.chat_models.bedrock import ChatBedrock
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser

if TYPE_CHECKING:
    from langchain.schema.runnable import Runnable
    from langchain_core.language_models.base import LanguageModelInput
    from langchain_core.language_models.chat_models import BaseChatModel
    from pydantic import BaseModel

    from llm.llm_call import LLMCall


class LLMHandler(ABC):
    """Abstract base class for handling LLM (Large Language Model) calls.

    Defines the interface for different LLM implementation handlers.
    """

    llm_call: LLMCall

    @abstractmethod
    def query(self, **kwargs: str) -> str | BaseModel:
        """Process a query using the configured LLM.

        Args:
            **kwargs: Keyword arguments to be passed to the LLM prompt template.

        Returns:
            str | BaseModel: The response from the LLM, either as a string or structured data.
        """


class LangChainHandler(LLMHandler):
    """Handler for LLM calls using the LangChain framework."""

    langchain_client: BaseChatModel
    chain: Runnable[LanguageModelInput, str | BaseModel]

    def __init__(self, llm_call: LLMCall) -> None:
        """Initialize the LLMHandler with an LLMCall and a Langchain ChatBedrock client.

        Args:
            llm_call (LLMCall): An LLMCall object containing the configuration for the LLM call.
        """
        self.llm_call = llm_call
        self._additional_messages: list[SystemMessage | HumanMessage] = []

        self.langchain_client = ChatBedrock(model_id=self.llm_call.model_id.value, temperature=self.llm_call.temp)
        self._configure_langchain_client()

    def _maybe_configure_retry(self) -> None:
        if self.llm_call.should_retry():
            self.langchain_client = self.langchain_client.with_retry(stop_after_attempt=self.llm_call.retry_limit, wait_exponential_jitter=True)

    def _configure_langchain_client(self) -> None:
        """Configure the LangChain client with structured output and retry settings."""
        # Apply retry configuration if needed
        self._maybe_configure_retry()

    def add_message(self, role: str, content: list[dict[str, Any]]) -> None:
        """Add a message to the handler's message chain.

        Args:
            role: The role of the message ("user" or "system")
            content: List of content dictionaries for LangChain multimodal input

        Raises:
            ValueError: If role is not "user" or "system"
        """
        if role not in ("user", "system"):
            error_msg = f"Invalid role '{role}'. Must be 'user' or 'system'"
            raise ValueError(error_msg)

        if role == "system":
            self._additional_messages.append(SystemMessage(content=content))
        else:  # role == "user"
            self._additional_messages.append(HumanMessage(content=content))

    @property
    def lc_prompt_tmplt(self) -> ChatPromptTemplate:
        """Property that returns the prompt template."""
        messages = []

        # Add system prompt template if exists
        if self.llm_call.system_prompt_tmplt is not None:
            messages.append(SystemMessagePromptTemplate.from_template(self.llm_call.system_prompt_tmplt))

        # Add human prompt template if exists
        if self.llm_call.human_prompt_tmplt is not None:
            messages.append(HumanMessagePromptTemplate.from_template(self.llm_call.human_prompt_tmplt))

        # Always add placeholder for additional messages to support dynamic message injection
        messages.append(MessagesPlaceholder(variable_name="additional_messages", optional=True))

        return ChatPromptTemplate.from_messages(messages)

    @property
    def llm_chain(self) -> Runnable[LanguageModelInput, str | BaseModel]:
        """Composes the prompt template with the llm."""
        return self.lc_prompt_tmplt | self.langchain_client

    @property
    def chain(self) -> Runnable[LanguageModelInput, str | BaseModel]:
        """The runnable chain that calls the LLM."""
        return self.llm_chain | StrOutputParser()

    def query(self, **kwargs: str) -> str:
        """Process a query using the configured LLM.

        Args:
            **kwargs: Keyword arguments to be passed to the LLM prompt template.

        Returns:
            str: The response from the LLM as a string.
        """
        # Ensure additional_messages is always present for the MessagesPlaceholder
        kwargs["additional_messages"] = kwargs.get("additional_messages", [])
        if self._additional_messages:
            # Append handler's messages to any passed in via kwargs
            kwargs["additional_messages"] = self._additional_messages + kwargs["additional_messages"]

        # Use the chain with the modified template that includes additional messages
        return self.chain.invoke(kwargs)

    def query_with_image(self, image_data: str, mime_type: str = "image/jpeg", **kwargs: str) -> str:
        """Process a query with an image using the configured LLM.

        Args:
            image_data: Base64-encoded image data.
            mime_type: MIME type of the image (default: "image/jpeg").
            **kwargs: Keyword arguments to be passed to the LLM prompt template.

        Returns:
            str: The response from the LLM as a string.
        """
        # Create temporary image message for this query only
        image_message = HumanMessage(content=[{"type": "image", "source_type": "base64", "data": image_data, "mime_type": mime_type}])

        return self.query(additional_messages=[image_message], **kwargs)


class StructuredLangChainHandler(LangChainHandler):
    """Handler for LLM calls that structures the output using a Pydantic model."""

    def __init__(self, llm_call: LLMCall, output_schema: BaseModel) -> None:
        """Initialize the handler with an LLM call and an output schema.

        Args:
            llm_call (LLMCall): An LLMCall object containing the configuration for the LLM call.
            output_schema (BaseModel): The Pydantic model to use for structuring the LLM output.
        """
        self.output_schema = output_schema
        super().__init__(llm_call=llm_call)

    def _configure_langchain_client(self) -> None:
        # Always use structured_output for all models (disable Claude 4 XML fallback)
        try:
            self.langchain_client = self.langchain_client.with_structured_output(self.output_schema)
        except (AttributeError, NotImplementedError, Exception):
            # Fall back to tool binding if structured_output isn't supported
            self.langchain_client = self.langchain_client.bind_tools([self.output_schema])

        super()._configure_langchain_client()

    @property
    def chain(self) -> Runnable[LanguageModelInput, BaseModel]:
        """The runnable chain that calls the LLM and parses the output to a structured format."""
        return self.llm_chain

    def query(self, **kwargs: str) -> BaseModel:
        """Process a query using the configured LLM.

        Args:
            **kwargs: Keyword arguments to be passed to the LLM prompt template.

        Returns:
            BaseModel: The response from the LLM as a structured Pydantic object.
        """
        # Add additional messages to kwargs if they exist
        kwargs["additional_messages"] = kwargs.get("additional_messages", [])
        if self._additional_messages:
            # Append new additional messages to existing ones
            kwargs["additional_messages"] = self._additional_messages + kwargs["additional_messages"]

        # Use the chain with the modified template that includes additional messages
        return self.chain.invoke(kwargs)

    def query_with_image(self, image_data: str, mime_type: str = "image/jpeg", **kwargs: str) -> BaseModel:
        """Process a query with an image using the configured LLM.

        Args:
            image_data: Base64-encoded image data.
            mime_type: MIME type of the image (default: "image/jpeg").
            **kwargs: Keyword arguments to be passed to the LLM prompt template.

        Returns:
            BaseModel: The response from the LLM as a structured Pydantic object.
        """
        # Create temporary image message for this query only
        image_message = HumanMessage(content=[{"type": "image", "source_type": "base64", "data": image_data, "mime_type": mime_type}])

        return self.query(additional_messages=[image_message], **kwargs)
