from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel
from aws_utils import AWSRegion, ClaudeModelId
from model_id import ModelID
from llm.llm_handler import LLMHandler


class LLMCall(BaseModel, ABC):
    def __init__(
        self,
        model_id: ModelID,
        sys_prompt_tmplt: str | None = None,
        human_prompt_tmplt: str | None = None,
        temp: float = 0.7,
        retry_limit: int | None = None,
    ) -> None:
        if sys_prompt_tmplt is None and human_prompt_tmplt is None:
            msg = "At least one of sys_prompt_tmplt or human_prompt_tmplt must be provided."
            raise ValueError(msg)
        self.sys_prompt_tmplt = sys_prompt_tmplt
        self.human_prompt_tmplt = human_prompt_tmplt
        self.model_id = model_id
        self.temp = temp
        self.retry_limit = retry_limit
        super().__init__()

    def to_dict(self) -> dict:
        raise NotImplementedError

    def from_dict(self, data: dict) -> None:
        raise NotImplementedError
    
    def to_json(self) -> str:
        raise NotImplementedError
    
    def from_json(self, data: str) -> None:
        raise NotImplementedError
    
    def should_retry(self) -> bool:
        return self.retry_limit is not None