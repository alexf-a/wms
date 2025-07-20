"""Custom output parser for Claude 4's XML-style function calling format."""

from __future__ import annotations
import json
import contextlib
import logging

from langchain_core.output_parsers import BaseOutputParser, XMLOutputParser
from pydantic import BaseModel
logger = logging.getLogger(__name__)

class Claude4XMLParsingError(Exception):
    """Exception raised when Claude 4 XML function call parsing fails."""


class Claude4XMLFunctionCallParser(BaseOutputParser):
    """Parser for Claude 4's XML-style function calling format.
    
    Claude 4 models return function calls in a custom XML format like:
    <function_calls>
    <invoke>
    <tool_name>ToolName</tool_name>
    <parameters>
    <param1>value1</param1>
    <param2>value2</param2>
    </parameters>
    </invoke>
    </function_calls>
    
    This parser extracts the parameters and returns them as a structured Pydantic object.
    """

    def __init__(self, output_schema: type[BaseModel]) -> None:
        """Initialize the parser with the expected output schema.
        
        Args:
            output_schema: The Pydantic model class to validate and structure the output.
                Will only be able to parse outputs for Pydantic models that have a maximum of one level of nesting.
                An output schema property can be a BaseModel or a list of BaseModels, but no further nesting is supported.
        """
        super().__init__()
        # No custom tag setup; use default XML parser
        self._xml_parser = XMLOutputParser()
        self._output_schema = output_schema

    @property
    def output_schema(self) -> type[BaseModel]:
        """Get the output schema for this parser."""
        return self._output_schema

    @output_schema.setter
    def output_schema(self, value: type[BaseModel]) -> None:
        """Set the output schema for this parser."""
        if not issubclass(value, BaseModel):
            msg = "output_schema must be a subclass of BaseModel"
            raise TypeError(msg)
        self._output_schema = value

    def parse(self, text: str) -> BaseModel:
        """Parse the XML function call format and return a structured object.

        Args:
            text: The raw text output from Claude 4 containing XML function calls.

        Returns:
            BaseModel: A Pydantic model instance with the parsed parameters.

        Raises:
            Claude4XMLParsingError: If the text doesn't contain valid function calls or parsing fails.
        """
        try:
            parsed_data: dict = self._xml_parser.parse(text)
            extracted_params = self._extract_parameters(parsed_data)
            # If any param is a JSON-like string, try to decode it
            for key, val in list(extracted_params.items()):
                if isinstance(val, str) and val.strip().startswith(("[", "{")):
                    with contextlib.suppress(json.JSONDecodeError):
                        extracted_params[key] = json.loads(val)
            return self._output_schema(**extracted_params)
        except Exception as e:
            msg = f"Failed to parse Claude 4 XML function call: {e}"
            logger.exception("Failed to parse and create output schema from text: %s", text)
            raise Claude4XMLParsingError(msg) from e

    def _extract_parameters(self, parsed_data: dict) -> dict:
        """Extract parameters from the parsed XML data.

        Args:
            parsed_data: The parsed XML data as a dictionary.

        Returns:
            dict: A dictionary of parameters extracted from the XML.
        """
        if "function_calls" not in parsed_data or not parsed_data["function_calls"]:
            msg = "No function calls found in the provided text."
            raise ValueError(msg)

        function_call = parsed_data["function_calls"][0]
        if "invoke" not in function_call:
            msg = "No invoke element found in the function call."
            raise ValueError(msg)

        invoke = function_call["invoke"]
        if "tool_name" not in invoke[0] or "parameters" not in invoke[1]:
            msg = "Invalid function call format."
            raise ValueError(msg)
        parameters = invoke[1]["parameters"]
        # Flatten the list of single-key dicts into one dict
        if isinstance(parameters, list):
            flat_params = {}
            for entry in parameters:
                if not isinstance(entry, dict):
                    msg = "Invalid parameter entry format."
                    raise TypeError(msg)
                flat_params.update(entry)
        else:
            flat_params = parameters

        return flat_params

    @property
    def _type(self) -> str:
        """Return the type of this parser."""
        return "claude4_xml_function_call"
