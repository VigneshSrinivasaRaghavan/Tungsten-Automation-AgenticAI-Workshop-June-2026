from typing import TypedDict, List, Dict

class TestCaseState(TypedDict):
    requirement: str
    conversation_history: List[Dict] # Short Term Memory
    past_patterns: str # Long Term Memory
    retrieved_context: str
    test_cases: List[Dict]
    errors: List[str]
    validation_status: str
    retry_count: int
    human_approval: str
    human_feedback: str