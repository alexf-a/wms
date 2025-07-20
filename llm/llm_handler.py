from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any
import json

from pydantic import TypeAdapter
from langchain.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
    MessagesPlaceholder,
)
from langchain_aws.chat_models.bedrock import ChatBedrock
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import SystemMessage, HumanMessage
from aws_utils.model_id import ClaudeModelID
from llm.claude4_xml_parser import Claude4XMLFunctionCallParser

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

    def __init__(
            self,
            llm_call: LLMCall
    ) -> None:
        """Initialize the LLMHandler with an LLMCall and a Langchain ChatBedrock client.

        Args:
            llm_call (LLMCall): An LLMCall object containing the configuration for the LLM call.
        """
        self.llm_call = llm_call
        self._additional_messages: list[SystemMessage | HumanMessage] = []

        self.langchain_client = ChatBedrock(
            model_id=self.llm_call.model_id.value,
            temperature=self.llm_call.temp
        )
        self._configure_langchain_client()

    def _maybe_configure_retry(self) -> None:
        if self.llm_call.should_retry():
            self.langchain_client = self.langchain_client.with_retry(
                stop_after_attempt=self.llm_call.retry_limit,
                wait_exponential_jitter=True
            )

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

        # Add placeholder for additional messages if they exist
        if self._additional_messages:
            messages.append(MessagesPlaceholder(variable_name="additional_messages"))

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
        # Add additional messages to kwargs if they exist
        if self._additional_messages:
            kwargs["additional_messages"] = self._additional_messages

        # Use the chain with the modified template that includes additional messages
        return self.chain.invoke(kwargs)


class StructuredLangChainHandler(LangChainHandler):
    """Handler for LLM calls that structures the output using a Pydantic model."""
    def __init__(self, llm_call: LLMCall, output_schema: BaseModel) -> None:
        """Initialize the handler with an LLM call and an output schema.

        Args:
            llm_call (LLMCall): An LLMCall object containing the configuration for the LLM call.
                # Note: The LLMCall system prompt template will be modified to include the output schema.
                 It should not contain any instructions about the output format.
            output_schema (BaseModel): The Pydantic model to use for structuring the LLM output.
        """
        self.output_schema = output_schema
        # merge with existing system prompt
        base = llm_call.system_prompt_tmplt.rstrip() if llm_call.system_prompt_tmplt else ""
        if llm_call.model_id == ClaudeModelID.CLAUDE_4_SONNET:
            instr = (
                "Please structure your XML output to match the following JSON schema. "
                "Make sure your XML output is recursively parseable "
                "(do not put JSON text inside of XML tags):\n{schema_str}"
            )
        else:
            instr = "Please format your output to match the following JSON schema:\n{schema_str}"
        llm_call.system_prompt_tmplt = (base + "\n\n" + instr).strip()
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
        if self.llm_call.model_id == ClaudeModelID.CLAUDE_4_SONNET:
            parser = Claude4XMLFunctionCallParser(self.output_schema)
            return self.llm_chain | parser
        return self.llm_chain

    def query(self, **kwargs: str) -> BaseModel:
        """Process a query using the configured LLM.

        Args:
            **kwargs: Keyword arguments to be passed to the LLM prompt template.

        Returns:
            BaseModel: The response from the LLM as a structured Pydantic object.
        """
        # generate JSON schema dict for the output model and serialize to string
        schema_dict = TypeAdapter(self.output_schema).json_schema()
        schema_str = json.dumps(schema_dict, indent=2)
        kwargs["schema_str"] = schema_str
        # Add additional messages to kwargs if they exist
        if self._additional_messages:
            kwargs["additional_messages"] = self._additional_messages

        # Use the chain with the modified template that includes additional messages
        return self.chain.invoke(kwargs)

