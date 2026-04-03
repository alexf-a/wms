from unittest.mock import MagicMock, patch

import pytest
from langchain.prompts import (
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
)
from langchain.schema.messages import HumanMessage, SystemMessage
from langchain_core.exceptions import OutputParserException
from pydantic import BaseModel, ValidationError

from aws_utils.model_id import ClaudeModelID
from aws_utils.region import AWSRegion
from lib.llm.gemini_model_id import GeminiModelID
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


class TestLangChainHandler:
    """Test cases for the LangChainHandler class."""

    def test_init_basic(self, llm_call: LLMCall, region: AWSRegion, mock_bedrock_client: MagicMock) -> None:
        """Test that LangChainHandler initializes correctly with basic parameters."""
        handler = LangChainHandler(llm_call, region)
        assert handler.llm_call == llm_call

        mock_bedrock_client.assert_called_once_with(
            model_id=llm_call.model_id.value,
            temperature=llm_call.temp,
            region=region.value,
        )

    def test_lc_prompt_tmplt_property(self, llm_call: LLMCall, region: AWSRegion, mock_bedrock_client: MagicMock) -> None:
        """Test that the lc_prompt_tmplt property returns a correctly configured ChatPromptTemplate."""
        handler = LangChainHandler(llm_call, region)
        prompt_template = handler.lc_prompt_tmplt

        messages = prompt_template.messages
        expected_message_count = 3
        assert len(messages) == expected_message_count

        assert isinstance(messages[0], SystemMessagePromptTemplate)
        assert messages[0].prompt.template == llm_call.system_prompt_tmplt
        assert isinstance(messages[1], HumanMessagePromptTemplate)
        assert messages[1].prompt.template == llm_call.human_prompt_tmplt
        assert isinstance(messages[2], MessagesPlaceholder)
        assert messages[2].variable_name == "additional_messages"

    def test_llm_chain_property(self, llm_call: LLMCall, region: AWSRegion, mock_bedrock_client: MagicMock) -> None:
        """Test that the llm_chain property returns a correctly configured Runnable."""
        handler = LangChainHandler(llm_call, region)
        prompt_mock = MagicMock()
        chain_result = "mock chain"
        prompt_mock.__or__.return_value = chain_result

        with patch("langchain.prompts.ChatPromptTemplate.from_messages", return_value=prompt_mock):
            result = handler.llm_chain

        prompt_mock.__or__.assert_called_once_with(handler.langchain_client)
        assert result == chain_result

    def test_query_method(self, llm_call: LLMCall, region: AWSRegion, mock_bedrock_client: MagicMock) -> None:
        """Test that the query method correctly invokes the chain."""
        handler = LangChainHandler(llm_call, region)
        with patch.object(LangChainHandler, "chain") as mock_chain:
            mock_chain.invoke.return_value = "Expected response"

            result = handler.query(question="What is the capital of France?")

        expected_kwargs = {
            "question": "What is the capital of France?",
            "additional_messages": [],
        }
        mock_chain.invoke.assert_called_once_with(expected_kwargs)
        assert result == "Expected response"

    def test_add_message_user_role(self, llm_call: LLMCall, region: AWSRegion, mock_bedrock_client: MagicMock) -> None:
        """Test that add_message correctly adds a user message."""
        handler = LangChainHandler(llm_call, region)

        multimodal_content = [
            {"type": "text", "text": "This is a test message."},
            {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": "fake_base64_data"},
            },
        ]

        handler.add_message("user", multimodal_content)

        assert len(handler._additional_messages) == 1
        message = handler._additional_messages[0]
        assert isinstance(message, HumanMessage)
        assert message.content == multimodal_content

    def test_add_message_system_role(self, llm_call: LLMCall, region: AWSRegion, mock_bedrock_client: MagicMock) -> None:
        """Test that add_message correctly adds a system message."""
        handler = LangChainHandler(llm_call, region)

        system_content = [{"type": "text", "text": "System instruction."}]
        handler.add_message("system", system_content)

        assert len(handler._additional_messages) == 1
        message = handler._additional_messages[0]
        assert isinstance(message, SystemMessage)
        assert message.content == system_content

    def test_add_message_invalid_role(self, llm_call: LLMCall, region: AWSRegion, mock_bedrock_client: MagicMock) -> None:
        """Test that add_message raises ValueError for invalid roles."""
        handler = LangChainHandler(llm_call, region)

        with pytest.raises(ValueError, match="Invalid role 'invalid'. Must be 'user' or 'system'"):
            handler.add_message("invalid", [{"type": "text", "text": "test"}])

    def test_lc_prompt_tmplt_with_additional_messages(
        self, llm_call: LLMCall, region: AWSRegion, mock_bedrock_client: MagicMock
    ) -> None:
        """Test that the prompt template always includes MessagesPlaceholder."""
        handler = LangChainHandler(llm_call, region)

        template = handler.lc_prompt_tmplt
        assert len(template.messages) == 3

        handler.add_message("user", [{"type": "text", "text": "test"}])

        updated_template = handler.lc_prompt_tmplt
        assert len(updated_template.messages) == 3
        placeholder_message = updated_template.messages[2]
        assert isinstance(placeholder_message, MessagesPlaceholder)
        assert placeholder_message.variable_name == "additional_messages"

    def test_query_with_multimodal_content(
        self, llm_call: LLMCall, region: AWSRegion, mock_bedrock_client: MagicMock
    ) -> None:
        """Test that query method handles multimodal content correctly."""
        handler = LangChainHandler(llm_call, region)

        multimodal_content = [
            {"type": "text", "text": "Image context"},
            {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": "test_image_data"},
            },
        ]
        handler.add_message("user", multimodal_content)

        with patch.object(LangChainHandler, "chain") as mock_chain:
            mock_chain.invoke.return_value = "Multimodal response"
            result = handler.query(question="What do you see?")

        expected_kwargs = {"question": "What do you see?", "additional_messages": handler._additional_messages}
        mock_chain.invoke.assert_called_once_with(expected_kwargs)
        assert result == "Multimodal response"

    def test_multiple_additional_messages(self, llm_call: LLMCall, region: AWSRegion, mock_bedrock_client: MagicMock) -> None:
        """Test that multiple additional messages are handled correctly."""
        handler = LangChainHandler(llm_call, region)

        handler.add_message("system", [{"type": "text", "text": "System context"}])
        handler.add_message("user", [{"type": "text", "text": "User message 1"}])
        handler.add_message(
            "user",
            [
                {"type": "text", "text": "User message with image"},
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": "img_data"},
                },
            ],
        )

        assert len(handler._additional_messages) == 3
        assert isinstance(handler._additional_messages[0], SystemMessage)
        assert isinstance(handler._additional_messages[1], HumanMessage)
        assert isinstance(handler._additional_messages[2], HumanMessage)

        template = handler.lc_prompt_tmplt
        assert len(template.messages) == 3
        assert isinstance(template.messages[2], MessagesPlaceholder)

    def test_query_with_image(self, llm_call: LLMCall, region: AWSRegion, mock_bedrock_client: MagicMock) -> None:
        """Test that query_with_image method correctly handles image data."""
        handler = LangChainHandler(llm_call, region)

        with patch.object(LangChainHandler, "chain") as mock_chain:
            mock_chain.invoke.return_value = "Image analysis response"

            image_data = "base64_encoded_image_data"
            mime_type = "image/png"
            result = handler.query_with_image(
                image_data=image_data,
                mime_type=mime_type,
                question="What do you see in this image?",
            )

        mock_chain.invoke.assert_called_once()
        call_args = mock_chain.invoke.call_args[0][0]
        assert call_args["question"] == "What do you see in this image?"
        additional_messages = call_args["additional_messages"]
        assert len(additional_messages) == 1

        image_message = additional_messages[0]
        assert isinstance(image_message, HumanMessage)
        assert len(image_message.content) == 1

        image_content = image_message.content[0]
        assert image_content["type"] == "image"
        assert image_content["source_type"] == "base64"
        assert image_content["data"] == image_data
        assert image_content["mime_type"] == mime_type
        assert result == "Image analysis response"

    def test_query_with_image_default_mime_type(
        self, llm_call: LLMCall, region: AWSRegion, mock_bedrock_client: MagicMock
    ) -> None:
        """Test that query_with_image uses default MIME type when not specified."""
        handler = LangChainHandler(llm_call, region)

        with patch.object(LangChainHandler, "chain") as mock_chain:
            mock_chain.invoke.return_value = "Default MIME type response"

            image_data = "base64_encoded_image_data"
            result = handler.query_with_image(image_data=image_data, question="Analyze this image")

        mock_chain.invoke.assert_called_once()
        call_args = mock_chain.invoke.call_args[0][0]
        additional_messages = call_args["additional_messages"]
        image_message = additional_messages[0]
        image_content = image_message.content[0]
        assert image_content["mime_type"] == "image/jpeg"
        assert result == "Default MIME type response"

    @patch("lib.llm.llm_handler.time.sleep")
    def test_query_transport_retry_success(
        self, mock_sleep: MagicMock, region: AWSRegion, mock_bedrock_client: MagicMock, system_prompt: str, model_id: ClaudeModelID
    ) -> None:
        """Transport errors are retried and can recover."""
        llm_call = LLMCall(system_prompt_tmplt=system_prompt, model_id=model_id, retry_limit=2)
        handler = LangChainHandler(llm_call, region)

        with patch.object(LangChainHandler, "chain") as mock_chain:
            mock_chain.invoke.side_effect = [RuntimeError("throttled"), "recovered"]
            result = handler.query(question="test")

        assert result == "recovered"
        assert mock_chain.invoke.call_count == 2
        mock_sleep.assert_called_once()

    @patch("lib.llm.llm_handler.time.sleep")
    def test_query_transport_retry_exhausted(
        self, mock_sleep: MagicMock, region: AWSRegion, mock_bedrock_client: MagicMock, system_prompt: str, model_id: ClaudeModelID
    ) -> None:
        """When all attempts fail with transport errors, re-raises the last one."""
        llm_call = LLMCall(system_prompt_tmplt=system_prompt, model_id=model_id, retry_limit=2)
        handler = LangChainHandler(llm_call, region)

        with patch.object(LangChainHandler, "chain") as mock_chain:
            mock_chain.invoke.side_effect = RuntimeError("service unavailable")
            with pytest.raises(RuntimeError, match="service unavailable"):
                handler.query(question="test")

        assert mock_chain.invoke.call_count == 3

    def test_query_no_retry_raises_immediately(
        self, llm_call: LLMCall, region: AWSRegion, mock_bedrock_client: MagicMock
    ) -> None:
        """Without retry configured, transport errors raise immediately."""
        handler = LangChainHandler(llm_call, region)

        with patch.object(LangChainHandler, "chain") as mock_chain:
            mock_chain.invoke.side_effect = RuntimeError("network error")
            with pytest.raises(RuntimeError, match="network error"):
                handler.query(question="test")

        assert mock_chain.invoke.call_count == 1

    @patch("lib.llm.llm_handler.time.sleep")
    @patch("lib.llm.llm_handler.time.monotonic")
    def test_query_timeout(
        self, mock_monotonic: MagicMock, mock_sleep: MagicMock, region: AWSRegion, mock_bedrock_client: MagicMock, system_prompt: str, model_id: ClaudeModelID
    ) -> None:
        """TimeoutError is raised when retry_timeout is exceeded."""
        llm_call = LLMCall(system_prompt_tmplt=system_prompt, model_id=model_id, retry_limit=5, retry_timeout=10.0)
        handler = LangChainHandler(llm_call, region)

        # First call: start=0.0, second: elapsed=11.0 > 10.0 timeout
        mock_monotonic.side_effect = [0.0, 11.0]

        with patch.object(LangChainHandler, "chain") as mock_chain:
            mock_chain.invoke.side_effect = RuntimeError("throttled")
            with pytest.raises(TimeoutError, match="10.0s timeout"):
                handler.query(question="test")

        assert mock_chain.invoke.call_count == 1


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
        self,
        structured_llm_call: LLMCall,
        output_schema: type[DummyOutputSchema],
        region: AWSRegion,
        mock_bedrock_client: MagicMock,
    ) -> None:
        """Test that StructuredLangChainHandler initializes correctly with an output schema."""
        handler = StructuredLangChainHandler(structured_llm_call, output_schema, region)

        assert handler.llm_call == structured_llm_call
        assert handler.output_schema == output_schema

        mock_bedrock_client.assert_called_once_with(
            model_id=structured_llm_call.model_id.value,
            temperature=structured_llm_call.temp,
            region=region.value,
        )

        mock_instance = mock_bedrock_client.return_value
        mock_instance.with_structured_output.assert_called_once_with(output_schema)

    def test_chain_property_returns_llm_chain(
        self,
        structured_llm_call: LLMCall,
        output_schema: type[DummyOutputSchema],
        region: AWSRegion,
        mock_bedrock_client: MagicMock,
    ) -> None:
        """Test that the chain property returns the llm_chain directly."""
        handler = StructuredLangChainHandler(structured_llm_call, output_schema, region)
        with patch.object(StructuredLangChainHandler, "llm_chain") as mock_llm_chain:
            assert handler.chain == mock_llm_chain

    def test_query_returns_structured_output(
        self,
        structured_llm_call: LLMCall,
        output_schema: type[DummyOutputSchema],
        region: AWSRegion,
        mock_bedrock_client: MagicMock,
    ) -> None:
        """Test that the query method returns structured output."""
        handler = StructuredLangChainHandler(structured_llm_call, output_schema, region)

        expected_field_value = 42
        mock_structured_output = DummyOutputSchema(field1="test", field2=expected_field_value)

        with patch.object(StructuredLangChainHandler, "chain") as mock_chain:
            mock_chain.invoke.return_value = mock_structured_output
            result = handler.query(question="What is structured output?")

        mock_chain.invoke.assert_called_once()
        call_args = mock_chain.invoke.call_args[0][0]
        assert call_args["question"] == "What is structured output?"
        assert call_args["additional_messages"] == []

        assert result == mock_structured_output
        assert isinstance(result, DummyOutputSchema)
        assert result.field1 == "test"
        assert result.field2 == expected_field_value

    def test_structured_handler_multimodal_support(
        self,
        structured_llm_call: LLMCall,
        output_schema: type[DummyOutputSchema],
        region: AWSRegion,
        mock_bedrock_client: MagicMock,
    ) -> None:
        """Test that StructuredLangChainHandler supports multimodal content."""
        handler = StructuredLangChainHandler(structured_llm_call, output_schema, region)

        multimodal_content = [
            {"type": "text", "text": "Analyze this image for structured output."},
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": "test_image_data_for_structured_output",
                },
            },
        ]
        handler.add_message("user", multimodal_content)

        template = handler.lc_prompt_tmplt
        assert len(template.messages) == 3
        assert isinstance(template.messages[2], MessagesPlaceholder)

        expected_output = DummyOutputSchema(field1="extracted_from_image", field2=99)

        with patch.object(StructuredLangChainHandler, "chain") as mock_chain:
            mock_chain.invoke.return_value = expected_output
            result = handler.query(question="Extract data from the image")

        mock_chain.invoke.assert_called_once()
        call_args = mock_chain.invoke.call_args[0][0]
        assert call_args["question"] == "Extract data from the image"
        assert call_args["additional_messages"] == handler._additional_messages
        assert result == expected_output

    def test_structured_handler_multiple_images(
        self,
        structured_llm_call: LLMCall,
        output_schema: type[DummyOutputSchema],
        region: AWSRegion,
        mock_bedrock_client: MagicMock,
    ) -> None:
        """Test structured handler with multiple images."""
        handler = StructuredLangChainHandler(structured_llm_call, output_schema, region)

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

        assert len(handler._additional_messages) == 2

        expected_output = DummyOutputSchema(field1="multi_image_analysis", field2=150)

        with patch.object(StructuredLangChainHandler, "chain") as mock_chain:
            mock_chain.invoke.return_value = expected_output
            result = handler.query(question="Compare the images")

        assert mock_chain.invoke.call_args[0][0]["additional_messages"] == handler._additional_messages
        assert result == expected_output

    def test_structured_query_with_image(
        self,
        structured_llm_call: LLMCall,
        output_schema: type[DummyOutputSchema],
        region: AWSRegion,
        mock_bedrock_client: MagicMock,
    ) -> None:
        """Test that StructuredLangChainHandler query_with_image returns structured output."""
        handler = StructuredLangChainHandler(structured_llm_call, output_schema, region)

        expected_output = DummyOutputSchema(field1="structured_image_analysis", field2=777)

        with patch.object(StructuredLangChainHandler, "chain") as mock_chain:
            mock_chain.invoke.return_value = expected_output
            image_data = "base64_encoded_structured_image_data"
            mime_type = "image/png"
            result = handler.query_with_image(
                image_data=image_data,
                mime_type=mime_type,
                context="Analyze this image for structured data",
                format_request="Extract key information",
            )

        mock_chain.invoke.assert_called_once()
        call_args = mock_chain.invoke.call_args[0][0]
        assert call_args["context"] == "Analyze this image for structured data"
        assert call_args["format_request"] == "Extract key information"

        additional_messages = call_args["additional_messages"]
        assert len(additional_messages) == 1

        image_message = additional_messages[0]
        assert isinstance(image_message, HumanMessage)
        assert len(image_message.content) == 1

        image_content = image_message.content[0]
        assert image_content["type"] == "image"
        assert image_content["source_type"] == "base64"
        assert image_content["data"] == image_data
        assert image_content["mime_type"] == mime_type

        assert result == expected_output
        assert isinstance(result, DummyOutputSchema)
        assert result.field1 == "structured_image_analysis"
        assert result.field2 == 777

    def test_structured_query_with_image_default_mime_type(
        self,
        structured_llm_call: LLMCall,
        output_schema: type[DummyOutputSchema],
        region: AWSRegion,
        mock_bedrock_client: MagicMock,
    ) -> None:
        """Test that StructuredLangChainHandler query_with_image uses default MIME type."""
        handler = StructuredLangChainHandler(structured_llm_call, output_schema, region)

        expected_output = DummyOutputSchema(field1="default_mime_structured", field2=333)

        with patch.object(StructuredLangChainHandler, "chain") as mock_chain:
            mock_chain.invoke.return_value = expected_output
            image_data = "base64_encoded_image_data"
            result = handler.query_with_image(
                image_data=image_data,
                instruction="Extract structured data from this image",
            )

        mock_chain.invoke.assert_called_once()
        call_args = mock_chain.invoke.call_args[0][0]
        additional_messages = call_args["additional_messages"]
        image_message = additional_messages[0]
        image_content = image_message.content[0]
        assert image_content["mime_type"] == "image/jpeg"

        assert result == expected_output
        assert isinstance(result, DummyOutputSchema)


# The abstract LLMHandler base class is indirectly tested through the concrete implementations above.


class TestStructuredReask:
    """Test cases for the reask loop in StructuredLangChainHandler."""

    @pytest.fixture(autouse=True)
    def _no_sleep(self) -> None:
        with patch("lib.llm.llm_handler.time.sleep"):
            yield

    @pytest.fixture
    def output_schema(self) -> type[DummyOutputSchema]:
        return DummyOutputSchema

    @pytest.fixture
    def llm_call_no_retry(self, system_prompt: str, model_id: ClaudeModelID) -> LLMCall:
        """LLMCall without retry (default behavior)."""
        return LLMCall(
            system_prompt_tmplt=system_prompt,
            model_id=model_id,
        )

    @pytest.fixture
    def llm_call_with_retry(self, system_prompt: str, model_id: ClaudeModelID) -> LLMCall:
        """LLMCall with retry_limit=2."""
        return LLMCall(
            system_prompt_tmplt=system_prompt,
            model_id=model_id,
            retry_limit=2,
        )

    def test_query_none_without_retry_raises(
        self,
        llm_call_no_retry: LLMCall,
        output_schema: type[DummyOutputSchema],
        region: AWSRegion,
        mock_bedrock_client: MagicMock,
    ) -> None:
        """When retry is disabled and invoke returns None, raises immediately."""
        handler = StructuredLangChainHandler(llm_call_no_retry, output_schema, region)

        with patch.object(StructuredLangChainHandler, "chain") as mock_chain:
            mock_chain.invoke.return_value = None
            with pytest.raises(OutputParserException, match="None"):
                handler.query()

        assert mock_chain.invoke.call_count == 1

    def test_query_none_with_retry_succeeds(
        self,
        llm_call_with_retry: LLMCall,
        output_schema: type[DummyOutputSchema],
        region: AWSRegion,
        mock_bedrock_client: MagicMock,
    ) -> None:
        """When invoke returns None then valid result, reask recovers."""
        handler = StructuredLangChainHandler(llm_call_with_retry, output_schema, region)
        valid_result = DummyOutputSchema(field1="ok", field2=1)

        with patch.object(StructuredLangChainHandler, "chain") as mock_chain:
            mock_chain.invoke.side_effect = [None, valid_result]
            result = handler.query()

        assert result == valid_result
        assert mock_chain.invoke.call_count == 2
        # Second call should have a reask message appended
        second_call_kwargs = mock_chain.invoke.call_args_list[1][0][0]
        reask_msgs = second_call_kwargs["additional_messages"]
        assert len(reask_msgs) == 1
        assert isinstance(reask_msgs[0], HumanMessage)
        assert "tool" in reask_msgs[0].content.lower()

    def test_query_validation_error_with_retry_succeeds(
        self,
        llm_call_with_retry: LLMCall,
        output_schema: type[DummyOutputSchema],
        region: AWSRegion,
        mock_bedrock_client: MagicMock,
    ) -> None:
        """When invoke raises ValidationError then returns valid, reask recovers."""
        handler = StructuredLangChainHandler(llm_call_with_retry, output_schema, region)
        valid_result = DummyOutputSchema(field1="ok", field2=1)

        # Create a real ValidationError by trying to validate bad data
        try:
            DummyOutputSchema(field1=123, field2="not_an_int")
        except ValidationError as e:
            validation_err = e

        with patch.object(StructuredLangChainHandler, "chain") as mock_chain:
            mock_chain.invoke.side_effect = [validation_err, valid_result]
            result = handler.query()

        assert result == valid_result
        assert mock_chain.invoke.call_count == 2
        second_call_kwargs = mock_chain.invoke.call_args_list[1][0][0]
        reask_msgs = second_call_kwargs["additional_messages"]
        assert len(reask_msgs) == 1
        assert "validation error" in reask_msgs[0].content.lower()

    def test_query_exhausts_reask_none(
        self,
        llm_call_with_retry: LLMCall,
        output_schema: type[DummyOutputSchema],
        region: AWSRegion,
        mock_bedrock_client: MagicMock,
    ) -> None:
        """When all attempts return None, raises OutputParserException."""
        handler = StructuredLangChainHandler(llm_call_with_retry, output_schema, region)

        with patch.object(StructuredLangChainHandler, "chain") as mock_chain:
            mock_chain.invoke.return_value = None
            with pytest.raises(OutputParserException, match="None"):
                handler.query()

        # 1 initial + 2 reasks = 3 total
        assert mock_chain.invoke.call_count == 3

    def test_query_exhausts_reask_validation_error(
        self,
        llm_call_with_retry: LLMCall,
        output_schema: type[DummyOutputSchema],
        region: AWSRegion,
        mock_bedrock_client: MagicMock,
    ) -> None:
        """When all attempts raise ValidationError, re-raises the last one."""
        handler = StructuredLangChainHandler(llm_call_with_retry, output_schema, region)

        try:
            DummyOutputSchema(field1=123, field2="not_an_int")
        except ValidationError as e:
            validation_err = e

        with patch.object(StructuredLangChainHandler, "chain") as mock_chain:
            mock_chain.invoke.side_effect = validation_err
            with pytest.raises(ValidationError):
                handler.query()

        assert mock_chain.invoke.call_count == 3

    def test_reask_messages_accumulate(
        self,
        llm_call_with_retry: LLMCall,
        output_schema: type[DummyOutputSchema],
        region: AWSRegion,
        mock_bedrock_client: MagicMock,
    ) -> None:
        """Each reask appends a new message, so they accumulate."""
        handler = StructuredLangChainHandler(llm_call_with_retry, output_schema, region)
        valid_result = DummyOutputSchema(field1="ok", field2=1)

        with patch.object(StructuredLangChainHandler, "chain") as mock_chain:
            mock_chain.invoke.side_effect = [None, None, valid_result]
            result = handler.query()

        assert result == valid_result
        assert mock_chain.invoke.call_count == 3
        # Third call should have 2 accumulated reask messages
        third_call_kwargs = mock_chain.invoke.call_args_list[2][0][0]
        reask_msgs = third_call_kwargs["additional_messages"]
        assert len(reask_msgs) == 2


class TestGeminiLangChainHandler:

    @pytest.fixture
    def gemini_model_id(self) -> GeminiModelID:
        return GeminiModelID.GEMINI_3_FLASH_PREVIEW

    @pytest.fixture
    def gemini_llm_call(self, system_prompt: str, human_prompt: str, gemini_model_id: GeminiModelID) -> LLMCall:
        return LLMCall(
            system_prompt_tmplt=system_prompt,
            human_prompt_tmplt=human_prompt,
            model_id=gemini_model_id,
        )

    def test_init_creates_gemini_client(self, gemini_llm_call: LLMCall, mock_gemini_client: MagicMock) -> None:
        handler = LangChainHandler(gemini_llm_call)
        assert handler.llm_call == gemini_llm_call
        mock_gemini_client.assert_called_once_with(
            model=gemini_llm_call.model_id.value,
            temperature=gemini_llm_call.temp,
        )

    def test_init_does_not_require_region(self, gemini_llm_call: LLMCall, mock_gemini_client: MagicMock) -> None:
        handler = LangChainHandler(gemini_llm_call)
        assert handler.llm_call == gemini_llm_call

    def test_bedrock_without_region_raises(self, llm_call: LLMCall) -> None:
        with pytest.raises(ValueError, match="region is required"):
            LangChainHandler(llm_call)

    def test_query_with_image_uses_image_url_format(
        self, gemini_llm_call: LLMCall, mock_gemini_client: MagicMock
    ) -> None:
        handler = LangChainHandler(gemini_llm_call)
        with patch.object(LangChainHandler, "chain") as mock_chain:
            mock_chain.invoke.return_value = "Gemini image response"
            image_data = "base64_encoded_image_data"
            mime_type = "image/png"
            handler.query_with_image(image_data=image_data, mime_type=mime_type)

        call_args = mock_chain.invoke.call_args[0][0]
        image_message = call_args["additional_messages"][0]
        assert isinstance(image_message, HumanMessage)
        image_content = image_message.content[0]
        assert image_content["type"] == "image_url"
        assert image_content["image_url"]["url"] == f"data:{mime_type};base64,{image_data}"


class TestGeminiStructuredHandler:

    @pytest.fixture
    def gemini_model_id(self) -> GeminiModelID:
        return GeminiModelID.GEMINI_3_FLASH_PREVIEW

    @pytest.fixture
    def output_schema(self) -> type[DummyOutputSchema]:
        return DummyOutputSchema

    @pytest.fixture
    def gemini_llm_call(self, system_prompt: str, gemini_model_id: GeminiModelID) -> LLMCall:
        return LLMCall(
            system_prompt_tmplt=system_prompt,
            model_id=gemini_model_id,
        )

    def test_structured_init_with_gemini(
        self, gemini_llm_call: LLMCall, output_schema: type[DummyOutputSchema], mock_gemini_client: MagicMock
    ) -> None:
        handler = StructuredLangChainHandler(gemini_llm_call, output_schema)
        assert handler.output_schema == output_schema
        mock_gemini_client.assert_called_once_with(
            model=gemini_llm_call.model_id.value,
            temperature=gemini_llm_call.temp,
        )
        mock_instance = mock_gemini_client.return_value
        mock_instance.with_structured_output.assert_called_once_with(output_schema)

    def test_structured_query_with_image_gemini_format(
        self, gemini_llm_call: LLMCall, output_schema: type[DummyOutputSchema], mock_gemini_client: MagicMock
    ) -> None:
        handler = StructuredLangChainHandler(gemini_llm_call, output_schema)
        expected_output = DummyOutputSchema(field1="gemini_result", field2=42)

        with patch.object(StructuredLangChainHandler, "chain") as mock_chain:
            mock_chain.invoke.return_value = expected_output
            result = handler.query_with_image(image_data="test_b64", mime_type="image/jpeg")

        call_args = mock_chain.invoke.call_args[0][0]
        image_message = call_args["additional_messages"][0]
        image_content = image_message.content[0]
        assert image_content["type"] == "image_url"
        assert image_content["image_url"]["url"] == "data:image/jpeg;base64,test_b64"
        assert result == expected_output


class TestTransportRetry:
    """Test cases for transport (non-reask) error retry in StructuredLangChainHandler."""

    @pytest.fixture(autouse=True)
    def _no_sleep(self) -> None:
        with patch("lib.llm.llm_handler.time.sleep"):
            yield

    @pytest.fixture
    def output_schema(self) -> type[DummyOutputSchema]:
        return DummyOutputSchema

    @pytest.fixture
    def llm_call_with_retry(self, system_prompt: str, model_id: ClaudeModelID) -> LLMCall:
        return LLMCall(
            system_prompt_tmplt=system_prompt,
            model_id=model_id,
            retry_limit=2,
        )

    @pytest.fixture
    def llm_call_no_retry(self, system_prompt: str, model_id: ClaudeModelID) -> LLMCall:
        return LLMCall(
            system_prompt_tmplt=system_prompt,
            model_id=model_id,
        )

    def test_transport_error_then_success_no_reask_message(
        self,
        llm_call_with_retry: LLMCall,
        output_schema: type[DummyOutputSchema],
        region: AWSRegion,
        mock_bedrock_client: MagicMock,
    ) -> None:
        """Transport errors retry with the same prompt — no reask message appended."""
        handler = StructuredLangChainHandler(llm_call_with_retry, output_schema, region)
        valid_result = DummyOutputSchema(field1="ok", field2=1)

        with patch.object(StructuredLangChainHandler, "chain") as mock_chain:
            mock_chain.invoke.side_effect = [RuntimeError("throttled"), valid_result]
            result = handler.query()

        assert result == valid_result
        assert mock_chain.invoke.call_count == 2
        # Key assertion: additional_messages must be empty on retry (no reask feedback)
        second_call_kwargs = mock_chain.invoke.call_args_list[1][0][0]
        assert second_call_kwargs["additional_messages"] == []

    def test_transport_error_exhausted_reraises(
        self,
        llm_call_with_retry: LLMCall,
        output_schema: type[DummyOutputSchema],
        region: AWSRegion,
        mock_bedrock_client: MagicMock,
    ) -> None:
        """When all attempts fail with transport errors, re-raises the last one."""
        handler = StructuredLangChainHandler(llm_call_with_retry, output_schema, region)

        with patch.object(StructuredLangChainHandler, "chain") as mock_chain:
            mock_chain.invoke.side_effect = RuntimeError("service unavailable")
            with pytest.raises(RuntimeError, match="service unavailable"):
                handler.query()

        # 1 initial + 2 retries = 3 total
        assert mock_chain.invoke.call_count == 3

    def test_transport_error_without_retry_raises_immediately(
        self,
        llm_call_no_retry: LLMCall,
        output_schema: type[DummyOutputSchema],
        region: AWSRegion,
        mock_bedrock_client: MagicMock,
    ) -> None:
        """Without retry configured, transport errors raise immediately."""
        handler = StructuredLangChainHandler(llm_call_no_retry, output_schema, region)

        with patch.object(StructuredLangChainHandler, "chain") as mock_chain:
            mock_chain.invoke.side_effect = RuntimeError("network error")
            with pytest.raises(RuntimeError, match="network error"):
                handler.query()

        assert mock_chain.invoke.call_count == 1


class TestConfigureEdgeCases:
    """Test cases for initialization edge cases and configuration branches."""

    @pytest.fixture
    def output_schema(self) -> type[DummyOutputSchema]:
        return DummyOutputSchema

    def test_structured_handler_falls_back_to_bind_tools(
        self,
        system_prompt: str,
        model_id: ClaudeModelID,
        region: AWSRegion,
        mock_bedrock_client: MagicMock,
    ) -> None:
        """When with_structured_output fails, falls back to bind_tools."""
        mock_instance = mock_bedrock_client.return_value
        mock_instance.with_structured_output.side_effect = NotImplementedError("not supported")

        llm_call = LLMCall(system_prompt_tmplt=system_prompt, model_id=model_id)
        handler = StructuredLangChainHandler(llm_call, DummyOutputSchema, region)

        mock_instance.with_structured_output.assert_called_once_with(DummyOutputSchema)
        mock_instance.bind_tools.assert_called_once_with([DummyOutputSchema])
        assert handler.output_schema == DummyOutputSchema

    def test_max_tokens_passed_to_bedrock_client(
        self,
        system_prompt: str,
        human_prompt: str,
        model_id: ClaudeModelID,
        region: AWSRegion,
        mock_bedrock_client: MagicMock,
    ) -> None:
        """When max_tokens is set, it is included in client parameters."""
        llm_call = LLMCall(
            system_prompt_tmplt=system_prompt,
            human_prompt_tmplt=human_prompt,
            model_id=model_id,
            max_tokens=1024,
        )
        LangChainHandler(llm_call, region)

        mock_bedrock_client.assert_called_once_with(
            model_id=model_id.value,
            temperature=llm_call.temp,
            region=region.value,
            max_tokens=1024,
        )

    def test_max_tokens_passed_to_gemini_client(
        self,
        system_prompt: str,
        human_prompt: str,
        mock_gemini_client: MagicMock,
    ) -> None:
        """When max_tokens is set on a Gemini call, it is included in client parameters."""
        gemini_model = GeminiModelID.GEMINI_3_FLASH_PREVIEW
        llm_call = LLMCall(
            system_prompt_tmplt=system_prompt,
            human_prompt_tmplt=human_prompt,
            model_id=gemini_model,
            max_tokens=2048,
        )
        LangChainHandler(llm_call)

        mock_gemini_client.assert_called_once_with(
            model=gemini_model.value,
            temperature=llm_call.temp,
            max_tokens=2048,
        )

    def test_prompt_template_with_no_human_prompt(
        self,
        system_prompt: str,
        model_id: ClaudeModelID,
        region: AWSRegion,
        mock_bedrock_client: MagicMock,
    ) -> None:
        """When human_prompt_tmplt is None, template has only system + placeholder."""
        llm_call = LLMCall(system_prompt_tmplt=system_prompt, model_id=model_id)
        handler = LangChainHandler(llm_call, region)

        template = handler.lc_prompt_tmplt
        assert len(template.messages) == 2
        assert isinstance(template.messages[0], SystemMessagePromptTemplate)
        assert isinstance(template.messages[1], MessagesPlaceholder)


class TestStructuredQueryWithImageException:
    """Test the exception logging path in StructuredLangChainHandler.query_with_image."""

    @pytest.fixture
    def output_schema(self) -> type[DummyOutputSchema]:
        return DummyOutputSchema

    def test_query_with_image_logs_and_reraises_exception(
        self,
        system_prompt: str,
        model_id: ClaudeModelID,
        output_schema: type[DummyOutputSchema],
        region: AWSRegion,
        mock_bedrock_client: MagicMock,
    ) -> None:
        """When query fails inside query_with_image, the exception is logged and re-raised."""
        llm_call = LLMCall(system_prompt_tmplt=system_prompt, model_id=model_id)
        handler = StructuredLangChainHandler(llm_call, output_schema, region)

        with (
            patch.object(StructuredLangChainHandler, "chain") as mock_chain,
            patch("lib.llm.llm_handler.logger") as mock_logger,
        ):
            mock_chain.invoke.side_effect = OutputParserException("bad output")
            with pytest.raises(OutputParserException, match="bad output"):
                handler.query_with_image(image_data="b64data")

        mock_logger.exception.assert_called_once()
        assert "FAILED" in mock_logger.exception.call_args[0][0]


class TestOutputParserExceptionReask:
    """Test that OutputParserException triggers reask (not naive retry)."""

    @pytest.fixture(autouse=True)
    def _no_sleep(self) -> None:
        with patch("lib.llm.llm_handler.time.sleep"):
            yield

    @pytest.fixture
    def output_schema(self) -> type[DummyOutputSchema]:
        return DummyOutputSchema

    @pytest.fixture
    def llm_call_with_retry(self, system_prompt: str, model_id: ClaudeModelID) -> LLMCall:
        return LLMCall(
            system_prompt_tmplt=system_prompt,
            model_id=model_id,
            retry_limit=2,
        )

    def test_output_parser_exception_triggers_reask(
        self,
        llm_call_with_retry: LLMCall,
        output_schema: type[DummyOutputSchema],
        region: AWSRegion,
        mock_bedrock_client: MagicMock,
    ) -> None:
        """OutputParserException is a reask exception — error feedback is appended."""
        handler = StructuredLangChainHandler(llm_call_with_retry, output_schema, region)
        valid_result = DummyOutputSchema(field1="recovered", field2=1)

        with patch.object(StructuredLangChainHandler, "chain") as mock_chain:
            mock_chain.invoke.side_effect = [
                OutputParserException("malformed tool call"),
                valid_result,
            ]
            result = handler.query()

        assert result == valid_result
        assert mock_chain.invoke.call_count == 2
        # Reask message should contain the error, not be empty like a naive retry
        second_call_kwargs = mock_chain.invoke.call_args_list[1][0][0]
        reask_msgs = second_call_kwargs["additional_messages"]
        assert len(reask_msgs) == 1
        assert isinstance(reask_msgs[0], HumanMessage)
        assert "validation error" in reask_msgs[0].content.lower()

    def test_output_parser_exception_exhausted_reraises(
        self,
        llm_call_with_retry: LLMCall,
        output_schema: type[DummyOutputSchema],
        region: AWSRegion,
        mock_bedrock_client: MagicMock,
    ) -> None:
        """When all attempts raise OutputParserException, re-raises the last one."""
        handler = StructuredLangChainHandler(llm_call_with_retry, output_schema, region)

        with patch.object(StructuredLangChainHandler, "chain") as mock_chain:
            mock_chain.invoke.side_effect = OutputParserException("persistent parse error")
            with pytest.raises(OutputParserException, match="persistent parse error"):
                handler.query()

        assert mock_chain.invoke.call_count == 3
