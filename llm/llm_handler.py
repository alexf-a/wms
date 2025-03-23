from abc import ABC, abstractmethod
from llm.llm_call import LLMCall
from llm.model_id import ModelID
from pydantic import BaseModel
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
from langchain_aws.chat_models.bedrock import ChatBedrock

from __future__ import annotations

chat = ChatBedrock(

)
class LLMHandler(ABC):
    llm_call: LLMCall
    @abstractmethod
    def query(self, **kwargs: str) -> str | BaseModel:
        pass

class LangChainHandler(LLMHandler):
    langchain_client: BaseChatModel
    chain: Runnable[LanguageModelInput, str | BaseModel]

    def __init__(
            self,
            llm_call: LLMCall
    ):
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
    def lc_prompt_tmplt(self):
        messages = []
        if self.llm_call.sys_prompt_tmplt is not None:
            messages.append(SystemMessagePromptTemplate.from_template(self.llm_call.sys_prompt_tmplt))

        if self.llm_call.human_prompt_tmplt is not None:
            messages.append(HumanMessagePromptTemplate.from_template(self.llm_call.human_prompt_tmplt))

        return ChatPromptTemplate.from_messages(messages)

    @property
    def llm_chain(self) -> Runnable[LanguageModelInput, str | BaseModel]:
        return self.lc_prompt_tmplt | self.langchain_client

    @property
    def chain(self) -> Runnable[LanguageModelInput, str | BaseModel]:
        return self.llm_chain | StrOutputParser()

    def query(self, **kwargs: str) -> str:
        return self.chain.invoke(kwargs)


class StructuredLangChainHandler(LangChainHandler):
    def __init__(self, llm_call: LLMCall, output_schema: BaseModel):
        super().__init__(llm_call)
        self.output_schema = output_schema
        self.langchain_client = self.langchain_client.with_structured_output(self.output_schema)

    @property
    def chain(self) -> Runnable[LanguageModelInput, BaseModel]:
        return self.llm_chain

