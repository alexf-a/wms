from collections.abc import Generator, MutableMapping
from unittest.mock import MagicMock, patch

import pytest
from langchain.schema.messages import SystemMessage, HumanMessage
from langchain.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from pydantic import BaseModel

from aws_utils.model_id import ClaudeModelID
from llm.llm_call import LLMCall
from llm.llm_handler import LangChainHandler, StructuredLangChainHandler


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
def model_id() -> ClaudeModelID:
    """Fixture providing a model ID for testing."""
    return ClaudeModelID.CLAUDE_3_5_HAIKU


@pytest.fixture
def llm_call(system_prompt: str, human_prompt: str, model_id: ClaudeModelID) -> LLMCall:
    """Fixture providing an LLMCall instance for testing."""
    return LLMCall(
        system_prompt_tmplt=system_prompt,
        human_prompt_tmplt=human_prompt,
        model_id=model_id,
    )


@pytest.fixture
def llm_call_with_retry(llm_call: LLMCall) -> LLMCall:
    """Fixture providing an LLMCall instance with retry configuration."""
    return LLMCall(
        system_prompt_tmplt=llm_call.system_prompt_tmplt,
        human_prompt_tmplt=llm_call.human_prompt_tmplt,
        model_id=llm_call.model_id,
        retry_limit=3,
        retry_timeout=10.0,
    )


@pytest.fixture
def mock_bedrock_client() -> Generator[MutableMapping, None, None]:
    """Fixture providing a mock ChatBedrock client."""
    with patch("llm.llm_handler.ChatBedrock") as mock_client:
        # Configure the mock to return predictable values
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        mock_instance.__or__.return_value = mock_instance  # Mock the | operator behavior
        mock_instance.invoke.return_value = "Mock LLM response"
        yield mock_client

class TestLangChainHandler:
    """Test cases for the LangChainHandler class."""

    def test_init_basic(self, llm_call: LLMCall, mock_bedrock_client: MutableMapping) -> None:
        """Test that LangChainHandler initializes correctly with basic parameters."""
        handler = LangChainHandler(llm_call)
        assert handler.llm_call == llm_call

        # Verify ChatBedrock was created with correct params
        mock_bedrock_client.assert_called_once_with(
            model_id=llm_call.model_id.value,
            temperature=llm_call.temp
        )

        # Verify retry not configured
        mock_instance = mock_bedrock_client.return_value
        assert not mock_instance.with_retry.called

    def test_init_with_retry(self, llm_call_with_retry: LLMCall, mock_bedrock_client: MutableMapping) -> None:
        """Test that LangChainHandler initializes correctly with retry configuration."""
        _ = LangChainHandler(llm_call_with_retry)

        # Verify ChatBedrock was created
        mock_bedrock_client.assert_called_once()

        # Verify retry was configured
        mock_instance = mock_bedrock_client.return_value
        mock_instance.with_retry.assert_called_once_with(
            stop_after_attempt=llm_call_with_retry.retry_limit,
            wait_exponential_jitter=True
        )

    def test_lc_prompt_tmplt_property(self, llm_call: LLMCall) -> None:
        """Test that the lc_prompt_tmplt property returns a correctly configured ChatPromptTemplate."""
        with patch("langchain_aws.chat_models.bedrock.ChatBedrock"):
            handler = LangChainHandler(llm_call)
            prompt_template = handler.lc_prompt_tmplt

            # Check it's a ChatPromptTemplate with the right messages
            messages = prompt_template.messages
            expected_message_count = 2
            assert len(messages) == expected_message_count

            # Check system message
            assert isinstance(messages[0], SystemMessagePromptTemplate)
            assert messages[0].prompt.template == llm_call.system_prompt_tmplt

            # Check human message
            assert isinstance(messages[1], HumanMessagePromptTemplate)
            assert messages[1].prompt.template == llm_call.human_prompt_tmplt

    def test_llm_chain_property(self, llm_call: LLMCall) -> None:
        """Test that the llm_chain property returns a correctly configured Runnable."""
        with patch("llm.llm_handler.ChatBedrock"):
            handler = LangChainHandler(llm_call)
            # Create a mock for what will be returned by the prompt template
            prompt_mock = MagicMock()
            chain_result = "mock chain"
            prompt_mock.__or__.return_value = chain_result

            # Instead of patching the property directly, patch ChatPromptTemplate.from_messages
            # which is used inside the lc_prompt_tmplt property
            with patch("langchain.prompts.ChatPromptTemplate.from_messages", return_value=prompt_mock):
                # Call the property under test
                result = handler.llm_chain

                # Verify the chain was composed correctly
                prompt_mock.__or__.assert_called_once_with(handler.langchain_client)
                assert result == chain_result

    def test_query_method(self, llm_call: LLMCall) -> None:
        """Test that the query method correctly invokes the chain."""
        with patch("llm.llm_handler.ChatBedrock"):
            handler = LangChainHandler(llm_call)
            with patch.object(LangChainHandler, "chain") as mock_chain:
                mock_chain.invoke.return_value = "Expected response"

                # Call the query method with a test parameter
                result = handler.query(question="What is the capital of France?")

                # Verify the chain was invoked with the correct parameters
                mock_chain.invoke.assert_called_once_with({"question": "What is the capital of France?"})
                assert result == "Expected response"


class TestStructuredLangChainHandler:
    """Test cases for the StructuredLangChainHandler class."""

    @pytest.fixture
    def output_schema(self) -> type[DummyOutputSchema]:
        """Fixture providing an output schema for testing."""
        return DummyOutputSchema

    @pytest.fixture
    def structured_llm_call(self, llm_call: LLMCall, output_schema: type[DummyOutputSchema]) -> LLMCall:
        """Fixture providing an LLMCall instance with an output schema."""
        return LLMCall(
            system_prompt_tmplt=llm_call.system_prompt_tmplt,
            human_prompt_tmplt=llm_call.human_prompt_tmplt,
            model_id=llm_call.model_id,
            output_schema=output_schema,
        )

    def test_init_with_schema(
        self, structured_llm_call: LLMCall, output_schema: type[DummyOutputSchema],
        mock_bedrock_client: MutableMapping
    ) -> None:
        """Test that StructuredLangChainHandler initializes correctly with an output schema."""
        handler = StructuredLangChainHandler(structured_llm_call, output_schema)

        # Verify basic properties
        assert handler.llm_call == structured_llm_call
        assert handler.output_schema == output_schema

        # Verify ChatBedrock was created
        mock_bedrock_client.assert_called_once()

        # Verify structured output was configured
        mock_instance = mock_bedrock_client.return_value
        mock_instance.with_structured_output.assert_called_once_with(output_schema)

    def test_chain_property_returns_llm_chain(
        self, structured_llm_call: LLMCall, output_schema: type[DummyOutputSchema]
    ) -> None:
        """Test that the chain property returns the llm_chain directly (no output parser)."""
        with patch("llm.llm_handler.ChatBedrock"), patch.object(StructuredLangChainHandler, "llm_chain") as mock_llm_chain:
            # Create a handler
            handler = StructuredLangChainHandler(structured_llm_call, output_schema)
            # Simply verify that chain returns the same object as llm_chain
            assert handler.chain == mock_llm_chain

    def test_query_returns_structured_output(
        self, structured_llm_call: LLMCall, output_schema: type[DummyOutputSchema]
    ) -> None:
        """Test that the query method returns structured output."""
        with patch("langchain_aws.chat_models.bedrock.ChatBedrock"):
            handler = StructuredLangChainHandler(structured_llm_call, output_schema)

            # Create a mock structured output
            expected_field_value = 42
            mock_structured_output = DummyOutputSchema(field1="test", field2=expected_field_value)

            with patch.object(StructuredLangChainHandler, "chain") as mock_chain:
                mock_chain.invoke.return_value = mock_structured_output

                # Call the query method
                result = handler.query(question="What is structured output?")

                # Verify chain was invoked and returned structured output
                mock_chain.invoke.assert_called_once_with({"question": "What is structured output?"})
                assert result == mock_structured_output
                assert isinstance(result, DummyOutputSchema)
                assert result.field1 == "test"
                assert result.field2 == expected_field_value


# No direct tests for the abstract LLMHandler class since it can't be instantiated,
# but its behavior is tested through the concrete implementations above
