from typing import TypedDict, List, Dict

class TestCaseState(TypedDict):
    """State for test case generation pipeline."""
    requirement: str
    retrieved_context: str
    test_cases: List[Dict]
    errors: List[str]