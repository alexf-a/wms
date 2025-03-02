from __future__ import annotations

from abc import ABC, abstractmethod

from langchain.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain.schema.runnable import Runnable
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.base import LanguageModelInput
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel


class LLMCall(BaseModel, ABC):
    """Abstract base class for executing language model calls.

    Attributes:
        system_prompt_tmplt (str): Template for the system prompt provided to the language model.
        human_prompt_tmplt (Optional[str]): Optional template for the human prompt input.
        output_schema (Optional[BaseModel]): Optional Pydantic model defining the expected 
            output schema.
        model_id (str): Identifier of the language model to be used.
        temp (float): Temperature parameter for the model generation (default is 0.7).
        retry_timeout (Optional[float]): Timeout value (in seconds) to wait before retrying 
            a failed call.
        retry_limit (Optional[int]): Maximum number of retry attempts allowed for executing 
            the call.

    Methods:
        execute(**kwargs) -> Union[str, BaseModel]:
            Abstract method to perform the language model call. Subclasses must implement
            this method to return either a string or an instance of a Pydantic BaseModel 
            based on the response.

    """

    system_prompt_tmplt: str
    human_prompt_tmplt: str | None = None
    output_schema: BaseModel | None = None
    model_id: str
    temp: float = 0.7
    retry_timeout: float | None = None
    retry_limit: int | None = None

    @abstractmethod
    def execute(self, **kwargs) -> str | BaseModel:
        """Execute an LLM call with the provided parameters.

        This method processes the LLM call based on the configured settings
        and returns the response.

        Args:
            **kwargs: Arbitrary keyword arguments passed to the LLM call.
                      These may include model-specific parameters.

        Returns:
            str | BaseModel: Either a string response from the LLM or a structured
                            response parsed into a BaseModel object.

        Example:
            >>> response = llm_instance.execute(joke_topic="dogs")
        """
        pass

class LangChainCall(LLMCall):
    langchain_client: BaseChatModel = None

    def __init__(
        self,
        system_prompt_tmplt: str,
        model_id: str,
        human_prompt_tmplt: str | None = None,
        output_schema: BaseModel | None = None,
        temp: float = 0.7,
        retry_timeout: float | None = None,
        retry_limit: int | None = None,
    ):
        super().__init__(
            system_prompt_tmplt=system_prompt_tmplt,
            human_prompt_tmplt=human_prompt_tmplt,
            output_schema=output_schema,
            model_id=model_id,
            temp=temp,
            retry_timeout=retry_timeout,
            retry_limit=retry_limit,
        )
        
        if self._is_anthropic_model(self.model_id):
            self.langchain_client = ChatAnthropic(
                model=self.model_id,
                temperature=self.temp,
            )
        else:
            raise NotImplementedError(f"Model {self.model_id} is not supported. Only Anthropic models are currently supported.")

    def _is_anthropic_model(model_id: str) -> bool:
        raise NotImplementedError

    @property
    def lc_prompt_tmplt(self):
        """Create a LangChain prompt template from the templates"""
        messages = [SystemMessagePromptTemplate.from_template(self.system_prompt_tmplt)]

        if self.human_prompt_tmplt:
            messages.append(HumanMessagePromptTemplate.from_template(self.human_prompt_tmplt))

        return ChatPromptTemplate.from_messages(messages)

    @property
    def chain(self) -> Runnable[LanguageModelInput, str | BaseModel]:
        llm = (
            self.langchain_client.with_structured_output(self.output_schema)
            if self.output_schema
            else self.langchain_client
        )
        chain = self.lc_prompt_tmplt | llm
        if self.output_schema is None:
            # Get the content from the AIMessage
            chain = chain | StrOutputParser()
        return chain

    def execute(self, **kwargs: str) -> str | BaseModel:
        return self.chain.invoke(kwargs)
