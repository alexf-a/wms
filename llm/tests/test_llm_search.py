# ruff: noqa
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wms.settings")
import django
django.setup()
import pytest

from schemas.llm_search import (
    ItemSearchCandidates,
    ItemSearchCandidate,
    ItemLocation,
)
from lib.llm.llm_search import get_item_location, HIGH_CONFIDENCE_THRESHOLD


def setup_monkeypatch(monkeypatch, dummy_instances):
    """Patch LLMCall, StructuredLangChainHandler, and Item.objects.filter for testing."""
    import lib.llm.llm_search as module

    # Patch LLMCall.from_json to avoid loading files
    monkeypatch.setattr(module.LLMCall, "from_json", lambda path: None)

    # Dummy handler to capture queries and return a fake ItemLocation
    class DummyHandler:
        def __init__(self, llm_call, output_schema):
            self.llm_call = llm_call
            self.output_schema = output_schema
            self.queries = []
            dummy_instances.append(self)

        def query(self, **kwargs):
            self.queries.append(kwargs)
            return ItemLocation(
                item_name="fake_item",
                bin_name="fake_bin",
                confidence="Medium",
                additional_info="fake_info",
            )

    monkeypatch.setattr(module, "StructuredLangChainHandler", DummyHandler)

    # Patch Item.objects.filter to return empty list (no real DB access)
    class DummyManager:
        @staticmethod
        def filter(*args, **kwargs):
            return []

    class DummyItem:
        objects = DummyManager()

    monkeypatch.setattr(module, "Item", DummyItem)


@pytest.mark.parametrize("confidences", [
    # A) more than one high confidence
    [HIGH_CONFIDENCE_THRESHOLD + 0.1, HIGH_CONFIDENCE_THRESHOLD + 0.2],
    # B) no high confidence
    [0.1, 0.2, HIGH_CONFIDENCE_THRESHOLD - 0.01],
])
def test_follow_up_query_called(monkeypatch, confidences):
    """Ensure get_item_location invokes a follow-up LLM query.

    A) more than one candidate has high confidence
    B) no candidate has high confidence
    """
    from unittest.mock import Mock
    from lib.llm.llm_search import _should_return_early

    dummy_instances = []
    setup_monkeypatch(monkeypatch, dummy_instances)

    # Build candidate models according to provided confidences
    candidates = [
        ItemSearchCandidate(name=f"Item{i}", bin_name=f"Bin{i}", confidence=conf)
        for i, conf in enumerate(confidences, start=1)
    ]
    candidates_model = ItemSearchCandidates(candidates=candidates)

    # Verify that _should_return_early returns False for these scenarios
    should_return_early: bool = _should_return_early(candidates_model)
    assert not should_return_early, "Should NOT return early for multiple/no high-confidence candidates"

    # Mock _should_return_early to verify it's called with correct arguments and returns False
    import lib.llm.llm_search as module
    mock_should_return_early = Mock(return_value=should_return_early)
    monkeypatch.setattr(module, "_should_return_early", mock_should_return_early)

    # Call the function under test
    result = get_item_location(candidates_model, user_id=123, user_query="where is it?")

    mock_should_return_early.assert_called_once_with(candidates_model)
    # Verify a follow-up handler was instantiated and query called
    assert len(dummy_instances) == 1, "StructuredLangChainHandler should be used once"
    handler = dummy_instances[0]
    assert hasattr(handler, "queries")
    assert len(handler.queries) == 1, "Follow-up query should be called exactly once"

    # Verify returned result is from DummyHandler.query
    assert isinstance(result, ItemLocation)
    assert result.item_name == "fake_item"
    assert result.bin_name == "fake_bin"
    assert result.confidence == "Medium"
    assert result.additional_info == "fake_info"

    # Verify query parameters passed to handler
    qargs = handler.queries[0]
    assert qargs.get("query") == "where is it?"
    assert qargs.get("formatted_context") == "[]"


@pytest.mark.parametrize("high_confidence", [
    # At threshold
    HIGH_CONFIDENCE_THRESHOLD,
    # Above threshold
    HIGH_CONFIDENCE_THRESHOLD + 0.01,
])
def test_single_high_confidence_direct_return(monkeypatch, high_confidence):
    """Ensure get_item_location returns direct ItemLocation for exactly one high-confidence candidate without follow-up."""
    from unittest.mock import Mock
    from lib.llm.llm_search import HIGH_CONFIDENCE_THRESHOLD, _should_return_early

    dummy_instances = []
    setup_monkeypatch(monkeypatch, dummy_instances)

    # One candidate at/above threshold, one below
    candidates = [
        ItemSearchCandidate(name="HighItem", bin_name="HighBin", confidence=high_confidence),
        ItemSearchCandidate(name="LowItem", bin_name="LowBin", confidence=HIGH_CONFIDENCE_THRESHOLD - 0.1),
    ]
    candidates_model = ItemSearchCandidates(candidates=candidates)
    should_return_early: bool = _should_return_early(candidates_model)
    assert should_return_early, "Should return early for exactly one high-confidence candidate"
        # Mock _should_return_early to verify it's called with correct arguments and returns True
    import lib.llm.llm_search as module
    mock_should_return_early = Mock(return_value=should_return_early)
    monkeypatch.setattr(module, "_should_return_early", mock_should_return_early)

    # Call the function under test
    result = get_item_location(candidates_model, user_id=456, user_query="anything")

    # Verify _should_return_early was called exactly once with the candidates
    mock_should_return_early.assert_called_once_with(candidates_model)

    # No follow-up handler should be instantiated
    assert len(dummy_instances) == 0, "StructuredLangChainHandler should not be used for single high-confidence candidate"

    # Verify returned result is built from the high-confidence candidate
    assert isinstance(result, ItemLocation)
    assert result.item_name == "HighItem"
    assert result.bin_name == "HighBin"
    assert result.confidence == "High"
    assert result.additional_info == f"Found with confidence score: {high_confidence}"


@pytest.mark.parametrize("confidences, expected", [
    # Single above threshold
    ([HIGH_CONFIDENCE_THRESHOLD + 0.01], True),
    # Exactly at threshold
    ([HIGH_CONFIDENCE_THRESHOLD], True),
    # Below threshold only
    ([HIGH_CONFIDENCE_THRESHOLD - 0.01], False),
    # Multiple above threshold
    ([HIGH_CONFIDENCE_THRESHOLD + 0.1, HIGH_CONFIDENCE_THRESHOLD + 0.2], False),
    # Empty list
    ([], False),
])
def test_should_return_early_helper(confidences, expected):
    """Test helper function for early return logic based on candidate confidences."""
    from lib.llm.llm_search import _should_return_early

    # Build ItemSearchCandidates from confidences
    candidates = [
        ItemSearchCandidate(name=f"I{i}", bin_name=f"B{i}", confidence=conf)
        for i, conf in enumerate(confidences)
    ]
    model = ItemSearchCandidates(candidates=candidates)
    assert _should_return_early(model) is expected


@pytest.mark.parametrize("scenario,confidences,expects_location_call", [
    # Single candidate at threshold - should return early (no location call)
    ("single_at_threshold", [HIGH_CONFIDENCE_THRESHOLD], False),
    # Single candidate above threshold - should return early (no location call)  
    ("single_above_threshold", [HIGH_CONFIDENCE_THRESHOLD + 0.01], False),
    # Single candidate below threshold - should make location call
    ("single_below_threshold", [HIGH_CONFIDENCE_THRESHOLD - 0.01], True),
    # Multiple candidates above threshold - should make location call
    ("multiple_above_threshold", [HIGH_CONFIDENCE_THRESHOLD + 0.1, HIGH_CONFIDENCE_THRESHOLD + 0.2], True),
    # No candidates above threshold - should make location call
    ("no_high_confidence", [0.1, 0.2, HIGH_CONFIDENCE_THRESHOLD - 0.01], True),
])
def test_perform_candidate_search_wiring(monkeypatch, scenario, confidences, expects_location_call) -> None:
    """Test that perform_candidate_search and get_item_location properly use global LLMCalls with correct arguments."""
    from lib.llm.llm_search import perform_candidate_search, get_item_location
    from typing import Any, Dict, Optional
    
    # Mock the global LLMCall instances
    class MockLLMCall:
        def __init__(self, name: str):
            self.name = name
    
    mock_candidates_llm_call = MockLLMCall("mock_candidates_llm_call")
    mock_location_llm_call = MockLLMCall("mock_location_llm_call")
    
    # Track handler calls separately for candidates and location
    candidates_handler_args: Optional[Dict[str, Any]] = None
    candidates_query_args: Optional[Dict[str, Any]] = None
    location_handler_args: Optional[Dict[str, Any]] = None
    location_query_args: Optional[Dict[str, Any]] = None
    
    class MockHandler:
        def __init__(self, llm_call: MockLLMCall, output_schema: type) -> None:
            nonlocal candidates_handler_args, location_handler_args
            if llm_call.name == "mock_candidates_llm_call":
                candidates_handler_args = {"llm_call": llm_call, "output_schema": output_schema}
            elif llm_call.name == "mock_location_llm_call":
                location_handler_args = {"llm_call": llm_call, "output_schema": output_schema}
        
        def query(self, **kwargs: Any):
            nonlocal candidates_query_args, location_query_args
            # Determine which handler this is based on the llm_call used to create it
            if hasattr(self, '_llm_call_name'):
                if self._llm_call_name == "mock_candidates_llm_call":
                    candidates_query_args = kwargs
                    return ItemSearchCandidates(candidates=[
                        ItemSearchCandidate(name=f"Item{i}", bin_name=f"Bin{i}", confidence=conf)
                        for i, conf in enumerate(confidences, start=1)
                    ])
                elif self._llm_call_name == "mock_location_llm_call":
                    location_query_args = kwargs
                    return ItemLocation(
                        item_name="MockLocationItem",
                        bin_name="MockLocationBin", 
                        confidence="Medium",
                        additional_info="Mock location info"
                    )
            else:
                # Fallback: determine by checking if this is the first call (candidates) or second (location)
                if candidates_query_args is None:
                    # First call - must be candidates
                    candidates_query_args = kwargs
                    return ItemSearchCandidates(candidates=[
                        ItemSearchCandidate(name=f"Item{i}", bin_name=f"Bin{i}", confidence=conf)
                        for i, conf in enumerate(confidences, start=1)
                    ])
                else:
                    # Second call - must be location
                    location_query_args = kwargs
                    return ItemLocation(
                        item_name="MockLocationItem",
                        bin_name="MockLocationBin", 
                        confidence="Medium",
                        additional_info="Mock location info"
                    )
    
    # Store original constructor to track which LLMCall is used
    original_init = MockHandler.__init__
    def tracked_init(self, llm_call: MockLLMCall, output_schema: type) -> None:
        self._llm_call_name = llm_call.name
        original_init(self, llm_call, output_schema)
    MockHandler.__init__ = tracked_init
    
    # Apply monkey patches
    import lib.llm.llm_search as module
    monkeypatch.setattr(module, "CANDIDATES_LLM_CALL", mock_candidates_llm_call)
    monkeypatch.setattr(module, "LOCATION_LLM_CALL", mock_location_llm_call)
    monkeypatch.setattr(module, "StructuredLangChainHandler", MockHandler)
    
    # Mock Item.objects.filter to return mock items
    class MockSearchInput:
        def __init__(self, name: str):
            self.name = name
        def to_prompt(self) -> str:
            return f"Item: {self.name}"
    
    class MockItem:
        def __init__(self, name: str) -> None:
            self.name = name
        
        def to_search_input(self) -> MockSearchInput:
            return MockSearchInput(self.name)
    
    class MockManager:
        @staticmethod
        def filter(*args: Any, **kwargs: Any) -> list[MockItem]:
            return [MockItem("TestItem1"), MockItem("TestItem2")]
    
    class MockItemModel:
        objects: MockManager = MockManager()
    
    monkeypatch.setattr(module, "Item", MockItemModel)
    
    # Test perform_candidate_search first
    user_query: str = "find my hammer"
    user_id: int = 123
    k: int = 5
    
    candidates_result: ItemSearchCandidates = perform_candidate_search(user_query, user_id, k)
    
    # Verify candidate search handler was created with correct global LLMCall
    assert candidates_handler_args is not None, "Candidates StructuredLangChainHandler should be instantiated"
    assert candidates_handler_args["llm_call"] == mock_candidates_llm_call, "Handler should be created with global CANDIDATES_LLM_CALL instance"
    assert candidates_handler_args["output_schema"] == ItemSearchCandidates, "Handler should use ItemSearchCandidates schema"
    
    # Verify candidate search query was called with correct arguments
    assert candidates_query_args is not None, "Candidates handler.query should be called"
    assert candidates_query_args["user_query"] == user_query, f"Expected user_query '{user_query}', got: {candidates_query_args.get('user_query')}"
    assert candidates_query_args["k"] == k, f"Expected k={k}, got: {candidates_query_args.get('k')}"
    
    # Verify formatted_context contains the expected item context
    formatted_context: Optional[str] = candidates_query_args.get("formatted_context")
    assert formatted_context is not None, "formatted_context should be provided"
    assert "TestItem1" in formatted_context, "Context should include TestItem1"
    assert "TestItem2" in formatted_context, "Context should include TestItem2"
    
    # Test get_item_location with the candidates
    location_query: str = "where is my item?"
    location_result: ItemLocation = get_item_location(candidates_result, user_id, location_query)
    
    if expects_location_call:
        # Verify location handler was created and called
        assert location_handler_args is not None, f"Location StructuredLangChainHandler should be instantiated for scenario: {scenario}"
        assert location_handler_args["llm_call"] == mock_location_llm_call, "Handler should be created with global LOCATION_LLM_CALL instance"
        assert location_handler_args["output_schema"] == ItemLocation, "Handler should use ItemLocation schema"
        
        assert location_query_args is not None, f"Location handler.query should be called for scenario: {scenario}"
        assert location_query_args["query"] == location_query, f"Expected query '{location_query}', got: {location_query_args.get('query')}"
        
        # Verify the result comes from the location handler
        assert location_result.item_name == "MockLocationItem", "Should return item from location handler"
        assert location_result.bin_name == "MockLocationBin", "Should return bin from location handler"
    else:
        # Verify location handler was NOT called (early return scenario)
        assert location_handler_args is None, f"Location StructuredLangChainHandler should NOT be instantiated for scenario: {scenario}"
        assert location_query_args is None, f"Location handler.query should NOT be called for scenario: {scenario}"
        
        # Verify the result comes from direct candidate mapping
        high_confidence_candidate = next(c for c in candidates_result.candidates if c.confidence >= HIGH_CONFIDENCE_THRESHOLD)
        assert location_result.item_name == high_confidence_candidate.name, "Should return item from high confidence candidate"
        assert location_result.bin_name == high_confidence_candidate.bin_name, "Should return bin from high confidence candidate"
        assert location_result.confidence == "High", "Should have High confidence for direct return"


def test_find_item_location_orchestration(monkeypatch):
    """Test that find_item_location calls perform_candidate_search and get_item_location in sequence."""
    from lib.llm.llm_search import find_item_location
    import lib.llm.llm_search as module
    from unittest.mock import Mock, call
    
    # Create mock candidates result
    mock_candidates = ItemSearchCandidates(candidates=[
        ItemSearchCandidate(name="TestItem", bin_name="TestBin", confidence=0.9)
    ])
    
    # Create mock location result
    mock_location = ItemLocation(
        item_name="TestItem",
        bin_name="TestBin", 
        confidence="High",
        additional_info="Test info"
    )
    
    # Mock perform_candidate_search
    mock_perform_candidate_search = Mock(return_value=mock_candidates)
    monkeypatch.setattr(module, "perform_candidate_search", mock_perform_candidate_search)
    
    # Mock get_item_location
    mock_get_item_location = Mock(return_value=mock_location)
    monkeypatch.setattr(module, "get_item_location", mock_get_item_location)
    
    # Test parameters
    user_query = "where is my hammer?"
    user_id = 123
    k = 5
    
    # Call find_item_location
    result = find_item_location(user_query, user_id, k)
    
    # Verify perform_candidate_search was called with correct arguments
    mock_perform_candidate_search.assert_called_once_with(user_query, user_id, k)
    
    # Verify get_item_location was called with the result from perform_candidate_search
    mock_get_item_location.assert_called_once_with(mock_candidates, user_id, user_query)
    
    # Verify the final result is returned from get_item_location
    assert result == mock_location
    assert result.item_name == "TestItem"
    assert result.bin_name == "TestBin"
    assert result.confidence == "High"
    assert result.additional_info == "Test info"
    
    # Approach 2: Using attach_mock for call order verification
    # Reset mocks for clean testing
    mock_perform_candidate_search.reset_mock()
    mock_get_item_location.reset_mock()
    
    # Create parent mock and attach child mocks
    parent_mock = Mock()
    parent_mock.attach_mock(mock_perform_candidate_search, 'perform_candidate_search')
    parent_mock.attach_mock(mock_get_item_location, 'get_item_location')
    
    # Call find_item_location again
    result3 = find_item_location(user_query, user_id, k)
    
    # Verify the exact sequence of calls
    expected_calls = [
        call.perform_candidate_search(user_query, user_id, k),
        call.get_item_location(mock_candidates, user_id, user_query)
    ]
    assert parent_mock.mock_calls == expected_calls, f"Expected calls: {expected_calls}, got: {parent_mock.mock_calls}"
    
    # Verify result is still correct
    assert result3 == mock_location
