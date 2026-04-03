from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from langchain.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
)
from langchain_aws.chat_models.bedrock import ChatBedrock
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import ValidationError

from lib.llm.gemini_model_id import GeminiModelID

logger = logging.getLogger(__name__)

# Exceptions that warrant a *reask* — sending the error back to the model so it
# can correct its output.  Everything else (throttling, network, etc.) gets a
# naive retry with the same prompt.
REASK_EXCEPTIONS: tuple[type[Exception], ...] = (
    ValidationError,
    OutputParserException,
)

if TYPE_CHECKING:
    from langchain.schema.runnable import Runnable
    from langchain_core.language_models.base import LanguageModelInput
    from langchain_core.language_models.chat_models import BaseChatModel
    from pydantic import BaseModel

    from aws_utils.region import AWSRegion
    from lib.llm.llm_call import LLMCall


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

    def __init__(self, llm_call: LLMCall, region: AWSRegion | None = None) -> None:
        """Initialize the LLMHandler with an LLMCall and a LangChain chat client.

        Args:
            llm_call (LLMCall): An LLMCall object containing the configuration for the LLM call.
            region (AWSRegion | None): The AWS region for ChatBedrock. Required for Claude models, ignored for Gemini.
        """
        self.llm_call = llm_call
        self._additional_messages: list[SystemMessage | HumanMessage] = []

        if isinstance(llm_call.model_id, GeminiModelID):
            client_params: dict[str, Any] = {
                "model": self.llm_call.model_id.value,
                "temperature": self.llm_call.temp,
            }
            if self.llm_call.max_tokens is not None:
                client_params["max_tokens"] = self.llm_call.max_tokens
            self.langchain_client = ChatGoogleGenerativeAI(**client_params)
        else:
            if region is None:
                msg = "region is required for Claude/Bedrock models"
                raise ValueError(msg)
            client_params = {
                "model_id": self.llm_call.model_id.value,
                "temperature": self.llm_call.temp,
                "region": region.value,
            }
            if self.llm_call.max_tokens is not None:
                client_params["max_tokens"] = self.llm_call.max_tokens
            self.langchain_client = ChatBedrock(**client_params)

        self._configure_langchain_client()

    def _maybe_configure_retry(self) -> None:
        if self.llm_call.should_retry():
            self.langchain_client = self.langchain_client.with_retry(stop_after_attempt=self.llm_call.retry_limit + 1, wait_exponential_jitter=True)

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

    def _build_image_content(self, image_data: str, mime_type: str) -> dict[str, Any]:
        """Build a provider-appropriate image content block.

        Args:
            image_data: Base64-encoded image data.
            mime_type: MIME type of the image.

        Returns:
            dict: Image content block in the format expected by the provider.
        """
        if isinstance(self.llm_call.model_id, GeminiModelID):
            return {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_data}"}}
        return {"type": "image", "source_type": "base64", "data": image_data, "mime_type": mime_type}

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
        image_message = HumanMessage(content=[self._build_image_content(image_data, mime_type)])

        return self.query(additional_messages=[image_message], **kwargs)


class StructuredLangChainHandler(LangChainHandler):
    """Handler for LLM calls that structures the output using a Pydantic model."""

    def __init__(self, llm_call: LLMCall, output_schema: BaseModel, region: AWSRegion | None = None) -> None:
        """Initialize the handler with an LLM call and an output schema.

        Args:
            llm_call (LLMCall): An LLMCall object containing the configuration for the LLM call.
            output_schema (BaseModel): The Pydantic model to use for structuring the LLM output.
            region (AWSRegion | None): The AWS region for ChatBedrock. Required for Claude models, ignored for Gemini.
        """
        self.output_schema = output_schema
        super().__init__(llm_call=llm_call, region=region)

    def _configure_langchain_client(self) -> None:
        # Do NOT call super() — the parent applies .with_retry() which wraps the
        # client in RunnableRetry and hides .with_structured_output().
        # Transport-level retry is handled in query() alongside reask logic.
        logger.info("[LLMHandler] Configuring structured output for schema: %s", self.output_schema.__name__)
        try:
            self.langchain_client = self.langchain_client.with_structured_output(self.output_schema)
            logger.info("[LLMHandler] Structured output configured successfully")
        except (AttributeError, NotImplementedError) as e:
            # Fall back to tool binding if structured_output isn't supported
            logger.warning("[LLMHandler] Falling back to bind_tools: %s", str(e))
            self.langchain_client = self.langchain_client.bind_tools([self.output_schema])

    @property
    def chain(self) -> Runnable[LanguageModelInput, BaseModel]:
        """The runnable chain that calls the LLM and parses the output to a structured format."""
        return self.llm_chain

    @staticmethod
    def _build_reask_message_for_none() -> HumanMessage:
        """Build a reask message when the model fails to produce a tool call."""
        return HumanMessage(content=(
            "Your previous response did not use the required tool/function call. "
            "You must respond by calling the provided tool with the appropriate arguments. "
            "Please try again."
        ))

    @staticmethod
    def _build_reask_message_for_error(exc: Exception) -> HumanMessage:
        """Build a reask message with specific validation errors."""
        return HumanMessage(content=(
            "Your previous tool call had validation errors. "
            f"Please fix the following issues and try again:\n{exc!s}"
        ))

    def _try_invoke(self, kwargs: dict[str, Any], attempt: int, retry_limit: int) -> BaseModel | None:
        """Attempt a single structured invocation.

        Handles two retry strategies:
        - *Reask*: For validation/parsing errors (REASK_EXCEPTIONS), sends the
          error back to the model so it can correct its output.
        - *Naive retry*: For transport/throttling errors (everything else),
          retries with the same prompt unchanged.

        Returns:
            BaseModel on success, None to signal the caller should retry.

        Raises:
            OutputParserException: On the final attempt when the model returns None.
            ValidationError: On the final attempt when validation fails.
            Exception: On the final attempt for transport errors.
        """
        try:
            result = self.chain.invoke(kwargs)
        except REASK_EXCEPTIONS as exc:
            if attempt < retry_limit:
                logger.warning(
                    "[LLMHandler] Reask %d/%d — validation error: %s",
                    attempt + 1, retry_limit, str(exc)[:200],
                )
                kwargs["additional_messages"] = kwargs["additional_messages"] + [
                    self._build_reask_message_for_error(exc)
                ]
                return None
            raise
        except Exception as exc:
            if attempt < retry_limit:
                logger.warning(
                    "[LLMHandler] Naive retry %d/%d — transport error: %s",
                    attempt + 1, retry_limit, str(exc)[:200],
                )
                return None
            raise

        if result is not None:
            return result

        if attempt < retry_limit:
            logger.warning(
                "[LLMHandler] Reask %d/%d — model returned None (no tool call)",
                attempt + 1, retry_limit,
            )
            kwargs["additional_messages"] = kwargs["additional_messages"] + [
                self._build_reask_message_for_none()
            ]
            return None

        msg = "Structured output returned None after all retry attempts"
        raise OutputParserException(msg)

    def query(self, **kwargs: str) -> BaseModel:
        """Process a query using the configured LLM, with retry on failure.

        On each failed attempt the method checks the exception type:
        - Reask exceptions (validation/parsing) → sends the error back to the
          model so it can self-correct.
        - All other exceptions (transport/throttling) → retries with the same
          prompt unchanged.

        Args:
            **kwargs: Keyword arguments to be passed to the LLM prompt template.

        Returns:
            BaseModel: The response from the LLM as a structured Pydantic object.

        Raises:
            OutputParserException: If the model returns None after all attempts.
            ValidationError: If the model produces invalid output after all attempts.
        """
        kwargs["additional_messages"] = kwargs.get("additional_messages", [])
        if self._additional_messages:
            kwargs["additional_messages"] = self._additional_messages + kwargs["additional_messages"]

        retry_limit = self.llm_call.retry_limit if self.llm_call.should_retry() else 0

        for attempt in range(1 + retry_limit):
            result = self._try_invoke(kwargs, attempt, retry_limit)
            if result is not None:
                return result

        msg = "Structured output returned None after all reask attempts"
        raise OutputParserException(msg)  # unreachable

    def query_with_image(self, image_data: str, mime_type: str = "image/jpeg", **kwargs: str) -> BaseModel:
        """Process a query with an image using the configured LLM.

        Args:
            image_data: Base64-encoded image data.
            mime_type: MIME type of the image (default: "image/jpeg").
            **kwargs: Keyword arguments to be passed to the LLM prompt template.

        Returns:
            BaseModel: The response from the LLM as a structured Pydantic object.
        """
        logger.info("[LLMHandler] query_with_image called, image_data length=%d, mime=%s", len(image_data), mime_type)
        # Create temporary image message for this query only
        image_message = HumanMessage(content=[self._build_image_content(image_data, mime_type)])

        try:
            result = self.query(additional_messages=[image_message], **kwargs)
        except Exception:
            logger.exception("[LLMHandler] query_with_image FAILED")
            raise
        else:
            logger.info("[LLMHandler] query_with_image succeeded, result type=%s", type(result).__name__)
            return result
