from __future__ import annotations

from typing import Any

from pydantic import BaseModel, field_serializer, field_validator

from lib.pydantic_utils import serialize_schema
from llm.model_id import ModelID  # noqa: TC001
from aws_utils.model_id import ClaudeModelID


class LLMCall(BaseModel):
    """A class for defining and executing calls to Language Models (LLMs)."""
    system_prompt_tmplt: str
    human_prompt_tmplt: str | None = None
    output_schema: type[BaseModel] | None = None
    model_id: ModelID
    temp: float = 0.7
    retry_timeout: float | None = None
    retry_limit: int | None = None

    model_config = {"arbitrary_types_allowed": True}

    @field_validator("model_id", mode="before")
    def validate_model_id(cls, value: str | ModelID) -> ModelID:  # noqa: N805
        """If provided model_id is a string, convert it via ModelID constructor."""
        if isinstance(value, str):
            return ClaudeModelID(value)
        return value

    @field_serializer("model_id")
    def serialize_model_id(self, model_id: ModelID) -> str:
        """Convert ModelID enum to its string value for serialization."""
        return model_id.value

    @field_serializer("output_schema")
    def serialize_output_schema(self, schema: type[BaseModel] | None) -> dict[str, Any] | None:
        """Convert Pydantic model class to a serializable representation."""
        if schema is None:
            return None
        return serialize_schema(schema)

    def should_retry(self) -> bool:
        """Check if retry configuration is enabled."""
        return self.retry_limit is not None and self.retry_timeout is not None




