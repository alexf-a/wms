from collections.abc import Generator, MutableMapping
from unittest.mock import MagicMock, patch

import pytest
from langchain.prompts import (
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
)
from langchain.schema.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from aws_utils.model_id import ClaudeModelID
from lib.llm.llm_call import LLMCall
from lib.llm.llm_handler import LangChainHandler, StructuredLangChainHandler


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
        mock_bedrock_client.assert_called_once_with(model_id=llm_call.model_id.value, temperature=llm_call.temp)

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
        mock_instance.with_retry.assert_called_once_with(stop_after_attempt=llm_call_with_retry.retry_limit, wait_exponential_jitter=True)

    def test_lc_prompt_tmplt_property(self, llm_call: LLMCall) -> None:
        """Test that the lc_prompt_tmplt property returns a correctly configured ChatPromptTemplate."""
        with patch("langchain_aws.chat_models.bedrock.ChatBedrock"):
            handler = LangChainHandler(llm_call)
            prompt_template = handler.lc_prompt_tmplt

            # Check it's a ChatPromptTemplate with the right messages
            messages = prompt_template.messages
            expected_message_count = 3  # system, human, and MessagesPlaceholder
            assert len(messages) == expected_message_count

            # Check system message
            assert isinstance(messages[0], SystemMessagePromptTemplate)
            assert messages[0].prompt.template == llm_call.system_prompt_tmplt

            # Check human message
            assert isinstance(messages[1], HumanMessagePromptTemplate)
            assert messages[1].prompt.template == llm_call.human_prompt_tmplt

            # Check MessagesPlaceholder
            assert isinstance(messages[2], MessagesPlaceholder)
            assert messages[2].variable_name == "additional_messages"

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
                expected_kwargs = {
                    "question": "What is the capital of France?",
                    "additional_messages": [],  # Always included, even when empty
                }
                mock_chain.invoke.assert_called_once_with(expected_kwargs)
                assert result == "Expected response"

    def test_add_message_user_role(self, llm_call: LLMCall) -> None:
        """Test that add_message correctly adds a user message."""
        with patch("llm.llm_handler.ChatBedrock"):
            handler = LangChainHandler(llm_call)

            # Test multimodal content
            multimodal_content = [
                {"type": "text", "text": "This is a test message."},
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "fake_base64_data"}},
            ]

            handler.add_message("user", multimodal_content)

            # Verify message was added
            assert len(handler._additional_messages) == 1
            message = handler._additional_messages[0]
            assert isinstance(message, HumanMessage)
            assert message.content == multimodal_content

    def test_add_message_system_role(self, llm_call: LLMCall) -> None:
        """Test that add_message correctly adds a system message."""
        with patch("llm.llm_handler.ChatBedrock"):
            handler = LangChainHandler(llm_call)

            system_content = [{"type": "text", "text": "System instruction."}]
            handler.add_message("system", system_content)

            # Verify message was added
            assert len(handler._additional_messages) == 1
            message = handler._additional_messages[0]
            assert isinstance(message, SystemMessage)
            assert message.content == system_content

    def test_add_message_invalid_role(self, llm_call: LLMCall) -> None:
        """Test that add_message raises ValueError for invalid roles."""
        with patch("llm.llm_handler.ChatBedrock"):
            handler = LangChainHandler(llm_call)

            with pytest.raises(ValueError, match="Invalid role 'invalid'. Must be 'user' or 'system'"):
                handler.add_message("invalid", [{"type": "text", "text": "test"}])

    def test_lc_prompt_tmplt_with_additional_messages(self, llm_call: LLMCall) -> None:
        """Test that the prompt template always includes MessagesPlaceholder."""
        with patch("llm.llm_handler.ChatBedrock"):
            handler = LangChainHandler(llm_call)

            # The template should always include MessagesPlaceholder
            template = handler.lc_prompt_tmplt
            assert len(template.messages) == 3

            # Add a message
            handler.add_message("user", [{"type": "text", "text": "test"}])

            # Template should still be the same
            updated_template = handler.lc_prompt_tmplt
            assert len(updated_template.messages) == 3

            # Check that the last message is a MessagesPlaceholder
            placeholder_message = updated_template.messages[2]
            assert isinstance(placeholder_message, MessagesPlaceholder)
            assert placeholder_message.variable_name == "additional_messages"

    def test_query_with_multimodal_content(self, llm_call: LLMCall) -> None:
        """Test that query method handles multimodal content correctly."""
        with patch("llm.llm_handler.ChatBedrock"):
            handler = LangChainHandler(llm_call)

            # Add multimodal message
            multimodal_content = [
                {"type": "text", "text": "Image context"},
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "test_image_data"}},
            ]
            handler.add_message("user", multimodal_content)

            with patch.object(LangChainHandler, "chain") as mock_chain:
                mock_chain.invoke.return_value = "Multimodal response"

                # Call query
                result = handler.query(question="What do you see?")

                # Verify that additional_messages were passed to the chain
                expected_kwargs = {"question": "What do you see?", "additional_messages": handler._additional_messages}
                mock_chain.invoke.assert_called_once_with(expected_kwargs)
                assert result == "Multimodal response"

    def test_multiple_additional_messages(self, llm_call: LLMCall) -> None:
        """Test that multiple additional messages are handled correctly."""
        with patch("llm.llm_handler.ChatBedrock"):
            handler = LangChainHandler(llm_call)

            # Add multiple messages
            handler.add_message("system", [{"type": "text", "text": "System context"}])
            handler.add_message("user", [{"type": "text", "text": "User message 1"}])
            handler.add_message(
                "user",
                [
                    {"type": "text", "text": "User message with image"},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "img_data"}},
                ],
            )

            # Verify all messages were stored
            assert len(handler._additional_messages) == 3
            assert isinstance(handler._additional_messages[0], SystemMessage)
            assert isinstance(handler._additional_messages[1], HumanMessage)
            assert isinstance(handler._additional_messages[2], HumanMessage)

            # Verify template includes placeholder
            template = handler.lc_prompt_tmplt
            assert len(template.messages) == 3
            assert isinstance(template.messages[2], MessagesPlaceholder)

    def test_query_with_image(self, llm_call: LLMCall) -> None:
        """Test that query_with_image method correctly handles image data."""
        with patch("llm.llm_handler.ChatBedrock"):
            handler = LangChainHandler(llm_call)

            # Mock the chain
            with patch.object(LangChainHandler, "chain") as mock_chain:
                mock_chain.invoke.return_value = "Image analysis response"

                # Call query_with_image
                image_data = "base64_encoded_image_data"
                mime_type = "image/png"
                result = handler.query_with_image(image_data=image_data, mime_type=mime_type, question="What do you see in this image?")

                # Verify the chain was called with the correct arguments
                mock_chain.invoke.assert_called_once()
                call_args = mock_chain.invoke.call_args[0][0]

                # Verify query parameters were passed
                assert call_args["question"] == "What do you see in this image?"

                # Verify additional_messages contains the image message
                assert "additional_messages" in call_args
                additional_messages = call_args["additional_messages"]
                assert len(additional_messages) == 1

                # Verify the image message structure
                image_message = additional_messages[0]
                assert isinstance(image_message, HumanMessage)
                assert len(image_message.content) == 1

                image_content = image_message.content[0]
                assert image_content["type"] == "image"
                assert image_content["source_type"] == "base64"
                assert image_content["data"] == image_data
                assert image_content["mime_type"] == mime_type

                # Verify the response
                assert result == "Image analysis response"

    def test_query_with_image_default_mime_type(self, llm_call: LLMCall) -> None:
        """Test that query_with_image uses default MIME type when not specified."""
        with patch("llm.llm_handler.ChatBedrock"):
            handler = LangChainHandler(llm_call)

            with patch.object(LangChainHandler, "chain") as mock_chain:
                mock_chain.invoke.return_value = "Default MIME type response"

                # Call query_with_image without specifying mime_type
                image_data = "base64_encoded_image_data"
                result = handler.query_with_image(image_data=image_data, question="Analyze this image")

                # Verify the chain was called
                mock_chain.invoke.assert_called_once()
                call_args = mock_chain.invoke.call_args[0][0]

                # Verify the image message uses default MIME type
                additional_messages = call_args["additional_messages"]
                image_message = additional_messages[0]
                image_content = image_message.content[0]
                assert image_content["mime_type"] == "image/jpeg"  # Default value

                assert result == "Default MIME type response"


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
        self, structured_llm_call: LLMCall, output_schema: type[DummyOutputSchema], mock_bedrock_client: MutableMapping
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

    def test_chain_property_returns_llm_chain(self, structured_llm_call: LLMCall, output_schema: type[DummyOutputSchema]) -> None:
        """Test that the chain property returns the llm_chain directly (no output parser)."""
        with patch("llm.llm_handler.ChatBedrock"), patch.object(StructuredLangChainHandler, "llm_chain") as mock_llm_chain:
            # Create a handler
            handler = StructuredLangChainHandler(structured_llm_call, output_schema)
            # Simply verify that chain returns the same object as llm_chain
            assert handler.chain == mock_llm_chain

    def test_query_returns_structured_output(self, structured_llm_call: LLMCall, output_schema: type[DummyOutputSchema]) -> None:
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

                # Verify chain was invoked with the correct parameters
                mock_chain.invoke.assert_called_once()
                call_args = mock_chain.invoke.call_args[0][0]

                # Check that required parameters are present
                assert call_args["question"] == "What is structured output?"
                assert call_args["additional_messages"] == []  # Empty but present

                assert result == mock_structured_output
                assert isinstance(result, DummyOutputSchema)
                assert result.field1 == "test"
                assert result.field2 == expected_field_value

    def test_structured_handler_multimodal_support(self, structured_llm_call: LLMCall, output_schema: type[DummyOutputSchema]) -> None:
        """Test that StructuredLangChainHandler supports multimodal content."""
        with patch("langchain_aws.chat_models.bedrock.ChatBedrock"):
            handler = StructuredLangChainHandler(structured_llm_call, output_schema)

            # Add multimodal content
            multimodal_content = [
                {"type": "text", "text": "Analyze this image for structured output."},
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "test_image_data_for_structured_output"}},
            ]
            handler.add_message("user", multimodal_content)

            # Verify prompt template includes MessagesPlaceholder
            template = handler.lc_prompt_tmplt
            assert len(template.messages) == 3
            assert isinstance(template.messages[2], MessagesPlaceholder)

            # Test query with multimodal content
            expected_output = DummyOutputSchema(field1="extracted_from_image", field2=99)

            with patch.object(StructuredLangChainHandler, "chain") as mock_chain:
                mock_chain.invoke.return_value = expected_output

                result = handler.query(question="Extract data from the image")

                # Verify additional_messages were passed
                mock_chain.invoke.assert_called_once()
                call_args = mock_chain.invoke.call_args[0][0]

                # Check that required parameters are present
                assert call_args["question"] == "Extract data from the image"
                assert call_args["additional_messages"] == handler._additional_messages

                assert result == expected_output

    def test_structured_handler_multiple_images(self, structured_llm_call: LLMCall, output_schema: type[DummyOutputSchema]) -> None:
        """Test structured handler with multiple images."""
        with patch("langchain_aws.chat_models.bedrock.ChatBedrock"):
            handler = StructuredLangChainHandler(structured_llm_call, output_schema)

            # Add multiple messages with images
            handler.add_message(
                "user",
                [
                    {"type": "text", "text": "First image context"},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "image1"}},
                ],
            )

            handler.add_message(
                "user",
                [
                    {"type": "text", "text": "Second image context"},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "image2"}},
                ],
            )

            # Verify both messages stored
            assert len(handler._additional_messages) == 2

            # Test query execution
            expected_output = DummyOutputSchema(field1="multi_image_analysis", field2=150)

            with patch.object(StructuredLangChainHandler, "chain") as mock_chain:
                mock_chain.invoke.return_value = expected_output

                result = handler.query(question="Compare the images")

                # Verify all messages passed to chain
                assert mock_chain.invoke.call_args[0][0]["additional_messages"] == handler._additional_messages
                assert result == expected_output

    def test_structured_query_with_image(self, structured_llm_call: LLMCall, output_schema: type[DummyOutputSchema]) -> None:
        """Test that StructuredLangChainHandler query_with_image method returns structured output."""
        with patch("langchain_aws.chat_models.bedrock.ChatBedrock"):
            handler = StructuredLangChainHandler(structured_llm_call, output_schema)

            # Mock the chain
            expected_output = DummyOutputSchema(field1="structured_image_analysis", field2=777)

            with patch.object(StructuredLangChainHandler, "chain") as mock_chain:
                mock_chain.invoke.return_value = expected_output

                # Call query_with_image
                image_data = "base64_encoded_structured_image_data"
                mime_type = "image/png"
                result = handler.query_with_image(
                    image_data=image_data,
                    mime_type=mime_type,
                    context="Analyze this image for structured data",
                    format_request="Extract key information",
                )

                # Verify the chain was called with the correct arguments
                mock_chain.invoke.assert_called_once()
                call_args = mock_chain.invoke.call_args[0][0]

                # Verify query parameters were passed
                assert call_args["context"] == "Analyze this image for structured data"
                assert call_args["format_request"] == "Extract key information"

                # Verify additional_messages contains the image message
                assert "additional_messages" in call_args
                additional_messages = call_args["additional_messages"]
                assert len(additional_messages) == 1

                # Verify the image message structure
                image_message = additional_messages[0]
                assert isinstance(image_message, HumanMessage)
                assert len(image_message.content) == 1

                image_content = image_message.content[0]
                assert image_content["type"] == "image"
                assert image_content["source_type"] == "base64"
                assert image_content["data"] == image_data
                assert image_content["mime_type"] == mime_type

                # Verify the response is structured
                assert result == expected_output
                assert isinstance(result, DummyOutputSchema)
                assert result.field1 == "structured_image_analysis"
                assert result.field2 == 777

    def test_structured_query_with_image_default_mime_type(self, structured_llm_call: LLMCall, output_schema: type[DummyOutputSchema]) -> None:
        """Test that StructuredLangChainHandler query_with_image uses default MIME type when not specified."""
        with patch("langchain_aws.chat_models.bedrock.ChatBedrock"):
            handler = StructuredLangChainHandler(structured_llm_call, output_schema)

            expected_output = DummyOutputSchema(field1="default_mime_structured", field2=333)

            with patch.object(StructuredLangChainHandler, "chain") as mock_chain:
                mock_chain.invoke.return_value = expected_output

                # Call query_with_image without specifying mime_type
                image_data = "base64_encoded_image_data"
                result = handler.query_with_image(image_data=image_data, instruction="Extract structured data from this image")

                # Verify the chain was called
                mock_chain.invoke.assert_called_once()
                call_args = mock_chain.invoke.call_args[0][0]

                # Verify the image message uses default MIME type
                additional_messages = call_args["additional_messages"]
                image_message = additional_messages[0]
                image_content = image_message.content[0]
                assert image_content["mime_type"] == "image/jpeg"  # Default value

                # Verify structured output
                assert result == expected_output
                assert isinstance(result, DummyOutputSchema)


# No direct tests for the abstract LLMHandler class since it can't be instantiated,
# but its behavior is tested through the concrete implementations above
