import sys
from collections.abc import Generator, MutableMapping
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aws_utils.region import AWSRegion

# Add the project root to the path so imports like 'from lib.llm.llm_call' work
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))


@pytest.fixture
def region() -> AWSRegion:
    """Return a default AWS region for tests."""
    return AWSRegion.US_WEST_2


@pytest.fixture
def mock_bedrock_client() -> Generator[MutableMapping, None, None]:
    """Provide a patched ChatBedrock client."""
    with patch("lib.llm.llm_handler.ChatBedrock") as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        mock_instance.__or__.return_value = mock_instance
        mock_instance.invoke.return_value = "Mock LLM response"
        yield mock_client
