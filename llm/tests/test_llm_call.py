from typing import Any

import pytest
from pydantic import BaseModel

from aws_utils.model_id import ClaudeModelID
from llm.llm_call import LLMCall


class DummyOutputSchema(BaseModel):
    """Output schema used for testing."""
    field1: str
    field2: int


@pytest.fixture
def system_prompt() -> str:
    """Fixture providing a system prompt for testing."""
    return "You are a helpful assistant."


@pytest.fixture
def human_prompt() -> str:
    """Fixture providing a human prompt for testing."""
    return "Answer this question: {question}"


@pytest.fixture
def temperature() -> float:
    """Fixture providing a temperature value for testing."""
    return 0.5


@pytest.fixture
def retry_timeout() -> float:
    """Fixture providing a retry timeout value for testing."""
    return 10.0


@pytest.fixture
def retry_limit() -> int:
    """Fixture providing a retry limit value for testing."""
    return 3


@pytest.fixture
def model_id() -> ClaudeModelID:
    """Fixture providing a model ID for testing."""
    return ClaudeModelID.CLAUDE_3_5_HAIKU


@pytest.fixture
def output_schema() -> type[DummyOutputSchema]:
    """Fixture providing an output schema for testing."""
    return DummyOutputSchema


@pytest.fixture
def llm_call_params(
    system_prompt: str,
    human_prompt: str,
    output_schema: type[DummyOutputSchema],
    model_id: ClaudeModelID,
    temperature: float,
    retry_timeout: float,
    retry_limit: int
) -> dict[str, Any]:
    """Fixture providing parameters for creating an LLMCall instance."""
    return {
        "system_prompt_tmplt": system_prompt,
        "human_prompt_tmplt": human_prompt,
        "output_schema": output_schema,
        "model_id": model_id,
        "temp": temperature,
        "retry_timeout": retry_timeout,
        "retry_limit": retry_limit,
    }


@pytest.fixture
def llm_call_instance(llm_call_params: dict[str, Any]) -> LLMCall:
    """Fixture providing an LLMCall instance for testing."""
    return LLMCall(**llm_call_params)


@pytest.fixture
def serialized_data(
    system_prompt: str,
    human_prompt: str,
    model_id: ClaudeModelID,
    temperature: float,
    retry_timeout: float,
    retry_limit: int
) -> dict[str, Any]:
    """Fixture providing serialized data for testing."""
    return {
        "system_prompt_tmplt": system_prompt,
        "human_prompt_tmplt": human_prompt,
        "model_id": model_id.value,
        "temp": temperature,
        "retry_timeout": retry_timeout,
        "retry_limit": retry_limit,
        "output_schema": None,
    }


def test_llm_call_serialization(
    llm_call_instance: LLMCall,
    system_prompt: str,
    human_prompt: str,
    model_id: ClaudeModelID,
    temperature: float,
    retry_timeout: float,
    retry_limit: int
) -> None:
    """Test that an LLMCall can be serialized to a dictionary."""
    serialized = llm_call_instance.model_dump()

    assert serialized["system_prompt_tmplt"] == system_prompt
    assert serialized["human_prompt_tmplt"] == human_prompt
    assert isinstance(serialized["output_schema"], dict)
    assert "class_name" in serialized["output_schema"]
    assert "module" in serialized["output_schema"]
    assert "fields" in serialized["output_schema"]
    assert serialized["model_id"] == model_id.value
    assert serialized["temp"] == temperature
    assert serialized["retry_timeout"] == retry_timeout
    assert serialized["retry_limit"] == retry_limit


def test_llm_call_deserialization(
    serialized_data: dict[str, Any],
    system_prompt: str,
    human_prompt: str,
    model_id: ClaudeModelID,
    temperature: float,
    retry_timeout: float,
    retry_limit: int
) -> None:
    """Test that an LLMCall can be deserialized from a dictionary."""
    llm_call = LLMCall.model_validate(serialized_data)

    assert llm_call.system_prompt_tmplt == system_prompt
    assert llm_call.human_prompt_tmplt == human_prompt
    assert llm_call.output_schema is None
    assert llm_call.model_id == model_id
    assert llm_call.temp == temperature
    assert llm_call.retry_timeout == retry_timeout
    assert llm_call.retry_limit == retry_limit


def test_model_id_serialization(model_id: ClaudeModelID) -> None:
    """Test that ModelID is properly serialized."""
    llm_call = LLMCall(
        system_prompt_tmplt="Test",
        model_id=model_id,
    )

    serialized = llm_call.model_dump()
    assert serialized["model_id"] == model_id.value


def test_model_id_deserialization(model_id: ClaudeModelID) -> None:
    """Test that ModelID is properly deserialized."""
    data = {
        "system_prompt_tmplt": "Test",
        "model_id": model_id.value,
    }

    llm_call = LLMCall.model_validate(data)
    assert llm_call.model_id == model_id


def test_output_schema_serialization(model_id: ClaudeModelID, output_schema: type[DummyOutputSchema]) -> None:
    """Test that output_schema is properly serialized."""
    llm_call = LLMCall(
        system_prompt_tmplt="Test",
        model_id=model_id,
        output_schema=output_schema,
    )

    serialized = llm_call.model_dump()
    assert isinstance(serialized["output_schema"], dict)
    assert "class_name" in serialized["output_schema"]
    assert serialized["output_schema"]["class_name"] == output_schema.__name__
    assert "module" in serialized["output_schema"]
    assert serialized["output_schema"]["module"] == output_schema.__module__
    assert "fields" in serialized["output_schema"]
    assert "field1" in serialized["output_schema"]["fields"]
    assert "field2" in serialized["output_schema"]["fields"]


def test_none_values(model_id: ClaudeModelID) -> None:
    """Test that None values are handled correctly."""
    llm_call = LLMCall(
        system_prompt_tmplt="Test",
        model_id=model_id,
        human_prompt_tmplt=None,
        output_schema=None,
        retry_timeout=None,
        retry_limit=None,
    )

    serialized = llm_call.model_dump()
    assert serialized["human_prompt_tmplt"] is None
    assert serialized["output_schema"] is None
    assert serialized["retry_timeout"] is None
    assert serialized["retry_limit"] is None

    deserialized = LLMCall.model_validate(serialized)
    assert deserialized.human_prompt_tmplt is None
    assert deserialized.output_schema is None
    assert deserialized.retry_timeout is None
    assert deserialized.retry_limit is None


def test_should_retry_both_params(
    model_id: ClaudeModelID,
    retry_timeout: float,
    retry_limit: int
) -> None:
    """Test the should_retry method when both params are set."""
    llm_call = LLMCall(
        system_prompt_tmplt="Test",
        model_id=model_id,
        retry_timeout=retry_timeout,
        retry_limit=retry_limit,
    )
    assert llm_call.should_retry() is True


def test_should_retry_limit_only(model_id: ClaudeModelID, retry_limit: int) -> None:
    """Test the should_retry method when only retry_limit is set."""
    llm_call = LLMCall(
        system_prompt_tmplt="Test",
        model_id=model_id,
        retry_limit=retry_limit,
    )
    assert llm_call.should_retry() is False


def test_should_retry_timeout_only(model_id: ClaudeModelID, retry_timeout: float) -> None:
    """Test the should_retry method when only retry_timeout is set."""
    llm_call = LLMCall(
        system_prompt_tmplt="Test",
        model_id=model_id,
        retry_timeout=retry_timeout,
    )
    assert llm_call.should_retry() is False


def test_json_structure(
    llm_call_instance: LLMCall,
    system_prompt: str,
    human_prompt: str,
    model_id: ClaudeModelID,
    temperature: float,
    retry_timeout: float,
    retry_limit: int
) -> None:
    """Test that the JSON structure of a serialized LLMCall is correct."""
    json_data = llm_call_instance.model_dump_json()
    # First, convert back to dict for easier assertions
    import json
    serialized = json.loads(json_data)
    
    # Check the structure of the serialized object
    assert isinstance(serialized, dict)
    
    # Check that all expected fields are present
    expected_fields = [
        "system_prompt_tmplt", 
        "human_prompt_tmplt", 
        "output_schema", 
        "model_id", 
        "temp", 
        "retry_timeout", 
        "retry_limit"
    ]
    for field in expected_fields:
        assert field in serialized
    
    # Check field types
    assert isinstance(serialized["system_prompt_tmplt"], str)
    assert isinstance(serialized["human_prompt_tmplt"], str)
    assert isinstance(serialized["output_schema"], dict)
    assert isinstance(serialized["model_id"], str)
    assert isinstance(serialized["temp"], float)
    assert isinstance(serialized["retry_timeout"], float)
    assert isinstance(serialized["retry_limit"], int)
    
    # Check output_schema structure
    schema = serialized["output_schema"]
    assert "class_name" in schema
    assert "module" in schema
    assert "fields" in schema
    
    fields = schema["fields"]
    assert "field1" in fields
    assert "field2" in fields
    
    # Check field information structure
    for field_name in ["field1", "field2"]:
        field_info = fields[field_name]
        assert "type" in field_info
        assert "required" in field_info
        assert "description" in field_info
        assert "default" in field_info
