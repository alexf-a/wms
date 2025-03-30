from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from langchain.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain_aws.chat_models.bedrock import ChatBedrock
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

    def __init__(
            self,
            llm_call: LLMCall
    ) -> None:
        """Initialize the LLMHandler with an LLMCall and a Langchain ChatBedrock client.

        Args:
            llm_call (LLMCall): An LLMCall object containing the configuration for the LLM call.
        """
        self.llm_call = llm_call
        self.langchain_client = ChatBedrock(
            model_id=self.llm_call.model_id.value,
            temperature=self.llm_call.temp
        )
        if self.llm_call.should_retry():
            self.langchain_client = self.langchain_client.with_retry(
                stop_after_attempt=self.llm_call.retry_limit,
                wait_exponential_jitter=True
            )

    @property
    def lc_prompt_tmplt(self) -> ChatPromptTemplate:
        """Property that returns the prompt template."""
        messages = []
        if self.llm_call.sys_prompt_tmplt is not None:
            messages.append(SystemMessagePromptTemplate.from_template(self.llm_call.sys_prompt_tmplt))

        if self.llm_call.human_prompt_tmplt is not None:
            messages.append(HumanMessagePromptTemplate.from_template(self.llm_call.human_prompt_tmplt))

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
        return self.chain.invoke(kwargs)


class StructuredLangChainHandler(LangChainHandler):
    """Handler for LLM calls that structures the output using a Pydantic model."""
    def __init__(self, llm_call: LLMCall, output_schema: BaseModel) -> None:
        """Initialize the handler with an LLM call and an output schema.

        Args:
            llm_call (LLMCall): An LLMCall object containing the configuration for the LLM call.
            output_schema (BaseModel): The Pydantic model to use for structuring the LLM output.
        """
        super().__init__(llm_call)
        self.output_schema = output_schema
        self.langchain_client = self.langchain_client.with_structured_output(self.output_schema)

    @property
    def chain(self) -> Runnable[LanguageModelInput, BaseModel]:
        """The runnable chain that calls the LLM and parses the output to a structured format."""
        return self.llm_chain

