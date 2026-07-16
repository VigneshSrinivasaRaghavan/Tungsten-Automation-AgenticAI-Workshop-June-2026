import json
from pathlib import Path
import pandas as pd
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from .state import TestCaseState
from src.core import get_langchain_llm, pick_requirement, search_vector_store, PersistentMemory
from src.prompts.testcase_prompts import TESTCASE_SYSTEM_PROMPT

# Create object for Persistent Memory
persistent_memory = PersistentMemory(collection_name="testcase_memory")

# Setup
ROOT = Path(__file__).resolve().parents[3]
REQ_DIR = ROOT / "data" / "requirements"
OUT_DIR = ROOT / "outputs" / "testcase_generated_hitl"
OUT_DIR.mkdir(parents=True, exist_ok=True)

llm = get_langchain_llm()
prompt_template = ChatPromptTemplate.from_messages([
    ("system", TESTCASE_SYSTEM_PROMPT),
    ("user", "Requirements:\n\n{requirement}")
])
parser = StrOutputParser()
chain = prompt_template | llm | parser

def read_requirement(state: TestCaseState) -> TestCaseState:
    """Read requirement file on first run. Skip if requirement already set by driver or follow-up."""
    if state.get("requirement"):
        if state.get("conversation_history"):
            # Actual follow-up — user typed an instruction in the CLI loop
            print(f"Follow-up instruction: {state['requirement'][:60]}...")
        else:
            # Requirement passed via CLI arg on first run
            print(f"Requirement loaded from file.")
        return {}
    req_file = pick_requirement(None, REQ_DIR)
    requirement = req_file.read_text(encoding="utf-8")
    return {"requirement": requirement}

def generate_tests(state: TestCaseState) -> TestCaseState:
    """Generate test cases using RAG + STM + LTM context."""
    requirement = state["requirement"]
    retrieved_context = state.get("retrieved_context", "")
    past_patterns = state.get("past_patterns", "")
    conversation_history = state.get("conversation_history", [])
    existing_test_cases = state.get("test_cases", [])  # restored from checkpoint by MemorySaver

    # Build conversation context from STM (last 6 messages)
    conversation_text = ""
    if conversation_history:
        lines = [f"{msg['role']}: {msg['content']}" for msg in conversation_history[-6:]]
        conversation_text = "\n".join(lines)

    # Compose prompt — three context sources + requirement
    user_message = f"""COMPANY TESTING GUIDELINES:
{retrieved_context}
"""
    if past_patterns:
        user_message += f"""
PAST TEST CASE PATTERNS (from previous sessions):
{past_patterns}
"""

    if conversation_history and existing_test_cases:
        # Follow-up mode — LLM must ADD to existing test cases, not regenerate
        existing_json = json.dumps(existing_test_cases, indent=2)
        user_message += f"""
CONVERSATION HISTORY (current session):
{conversation_text}

EXISTING TEST CASES (already generated in this session):
{existing_json}

FOLLOW-UP INSTRUCTION: {requirement}
Add the requested test cases to the existing list above.
Return ALL test cases (existing + new ones) as a single JSON array.
Do NOT regenerate existing ones — only append new ones with the next available TC IDs.
"""
    else:
        # First run — generate fresh
        user_message += f"""
REQUIREMENT:
{requirement}
"""

    try:
        response = chain.invoke({"requirement": user_message})
        testcases = json.loads(response)

        # Update STM — append this turn to conversation history
        updated_history = list(conversation_history)
        updated_history.append({"role": "user", "content": requirement})
        tc_ids = ", ".join(tc.get("id", "") for tc in testcases)
        updated_history.append({
            "role": "agent",
            "content": f"Generated {len(testcases)} test case(s): {tc_ids}"
        })

        return {
            "test_cases": testcases,
            "errors": [],
            "conversation_history": updated_history
        }

    except json.JSONDecodeError as e:
        return {"test_cases": [], "errors": [f"JSON parse error: {e}"]}
    except Exception as e:
        return {"test_cases": [], "errors": [f"LLM error: {e}"]}


def save_outputs(state: TestCaseState) -> TestCaseState:
    """Save test cases to files. LTM save happens in driver after user confirms."""
    from datetime import datetime
    test_cases = state["test_cases"]

    if not test_cases:
        return {}

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save raw JSON — timestamped so sessions don't overwrite each other
    raw_file = OUT_DIR / f"raw_output_{timestamp}.txt"
    raw_file.write_text(json.dumps(test_cases, indent=2), encoding="utf-8")

    # Save CSV — timestamped
    df = pd.DataFrame(test_cases)
    if "steps" in df.columns:
        df["steps"] = df["steps"].apply(
            lambda x: " | ".join(x) if isinstance(x, list) else x
        )
    csv_file = OUT_DIR / f"test_cases_{timestamp}.csv"
    df.to_csv(csv_file, index=False)

    print(f"Saved {len(test_cases)} test cases to {OUT_DIR}")
    return {}


def validate_tests(state: TestCaseState) -> TestCaseState:
    """Validate generated test cases."""
    test_cases = state.get("test_cases", [])

    print("Validating test cases...")

    # Validation checks
    if len(test_cases) < 3:
        print("Validation FAILED: Less than 3 test cases")
        return {"validation_status": "fail"}

    # Check each test case has required fields
    required_fields = ["id", "title", "steps", "expected", "priority"]
    for tc in test_cases:
        missing = [f for f in required_fields if f not in tc or not tc[f]]
        if missing:
            print(f"Validation FAILED: Missing fields {missing}")
            return {"validation_status": "fail"}

        # Check steps is a list with at least 2 steps
        if not isinstance(tc["steps"], list) or len(tc["steps"]) < 2:
            print("Validation FAILED: Steps must be list with 2+ items")
            return {"validation_status": "fail"}

    print("✅ Validation PASSED")
    return {"validation_status": "pass"}


def retry_generate(state: TestCaseState) -> TestCaseState:
    """Retry test case generation with RAG context."""
    retry_count = state.get("retry_count", 0) + 1
    print(f"🔄 Retry attempt {retry_count}/3")

    requirement = state["requirement"]
    context = state.get("retrieved_context", "")

    # Build enhanced prompt with context
    user_message = f"""Based on the following company testing guidelines:

{context}

---

Now generate test cases for this requirement:

{requirement}"""

    try:
        response = chain.invoke({"requirement": user_message})
        testcases = json.loads(response)
        print(f"Regenerated {len(testcases)} test cases with RAG")

        return {
            "test_cases": testcases,
            "errors": [],
            "retry_count": retry_count,
            "validation_status": "pending"
        }

    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON: {e}")
        return {
            "test_cases": [],
            "errors": [f"JSON parse error: {e}"],
            "retry_count": retry_count,
            "validation_status": "fail"
        }
    except Exception as e:
        print(f"LLM call failed: {e}")
        return {
            "test_cases": [],
            "errors": [f"LLM error: {e}"],
            "retry_count": retry_count,
            "validation_status": "fail"
        }

def route_after_validation(state: TestCaseState) -> str:
    """Decide next node based on validation result."""

    validation_status = state.get("validation_status", "pending")
    retry_count = state.get("retry_count", 0)

    # If passed validation → show preview for human approval
    if validation_status == "pass":
        print("✅ Routing to PREVIEW (for human approval)")
        return "preview"  # Changed from "save" to "preview"

    # If failed but can retry → retry
    if validation_status == "fail" and retry_count < 3:
        print(f"⚠️ Routing to RETRY (attempt {retry_count + 1}/3)")
        return "retry"

    # If max retries reached → show preview anyway (human decides)
    print("❌ Max retries reached, routing to PREVIEW")
    return "preview"  # Changed from "save" to "preview"

def show_preview(state: TestCaseState) -> TestCaseState:
    """Show test cases preview to human for approval."""
    test_cases = state.get("test_cases", [])

    print("\n" + "="*60)
    print("📋 TEST CASES PREVIEW - AWAITING APPROVAL")
    print("="*60)

    for i, tc in enumerate(test_cases, 1):
        print(f"\n[{i}] {tc.get('id', 'N/A')}: {tc.get('title', 'N/A')}")
        print(f"    Priority: {tc.get('priority', 'N/A')}")
        print(f"    Steps: {len(tc.get('steps', []))} steps")
        print(f"    Expected: {tc.get('expected', 'N/A')[:50]}...")

    print("\n" + "="*60)
    print(f"Total: {len(test_cases)} test cases generated")
    print("="*60 + "\n")

    print(f"Preview shown: {len(test_cases)} test cases")
    return {"human_approval": "pending"}

def human_approval(state: TestCaseState) -> TestCaseState:
    """Wait for human approval decision."""

    print("\n🤔 What would you like to do?")
    print("  1. APPROVE - Save test cases")
    print("  2. REJECT - Regenerate test cases")
    print("  3. VIEW - Show full details")

    while True:
        choice = input("\nEnter choice (1/2/3): ").strip()

        if choice == "1":
            print("✅ Human APPROVED test cases")
            return {
                "human_approval": "approved",
                "human_feedback": "Approved by user"
            }

        elif choice == "2":
            feedback = input("Why reject? (optional): ").strip()
            print(f"❌ Human REJECTED test cases: {feedback}")
            return {
                "human_approval": "rejected",
                "human_feedback": feedback or "No feedback provided"
            }

        elif choice == "3":
            _show_full_details(state)
            continue  # Ask again

        else:
            print("❌ Invalid choice. Please enter 1, 2, or 3.")

def _show_full_details(state: TestCaseState):
    """Show complete test case details."""
    test_cases = state.get("test_cases", [])

    print("\n" + "="*60)
    print("📝 FULL TEST CASE DETAILS")
    print("="*60)

    for i, tc in enumerate(test_cases, 1):
        print(f"\n{'─'*60}")
        print(f"Test Case #{i}")
        print(f"{'─'*60}")
        print(f"ID:       {tc.get('id', 'N/A')}")
        print(f"Title:    {tc.get('title', 'N/A')}")
        print(f"Priority: {tc.get('priority', 'N/A')}")
        print(f"\nSteps:")
        for j, step in enumerate(tc.get('steps', []), 1):
            print(f"  {j}. {step}")
        print(f"\nExpected Result:")
        print(f"  {tc.get('expected', 'N/A')}")

    print("\n" + "="*60 + "\n")
    
def route_after_human_approval(state: TestCaseState) -> str:
    """Decide next node based on human decision."""

    approval = state.get("human_approval", "pending")

    if approval == "approved":
        print("✅ Human approved - routing to SAVE")
        return "save"

    elif approval == "rejected":
        print("❌ Human rejected - routing to RETRY")
        return "retry"

    else:
        print("⚠️ Unknown approval status - routing to SAVE")
        return "save"

def retrieve_context(state: TestCaseState) -> TestCaseState:
    """Retrieve relevant testing guidelines from knowledge base."""

    requirement = state["requirement"]
    print("Retrieving relevant testing guidelines...")

    # Search vector store
    results = search_vector_store(
        query=f"test case guidelines for: {requirement[:200]}",
        top_k=3
    )

    # Format context
    context_parts = []
    for i, (doc, score) in enumerate(results, 1):
        source = doc.metadata.get('source', 'Unknown').split('/')[-1]
        similarity = 1 - score

        print(f"Retrieved [{i}] {source} (similarity: {similarity:.2f})")

        context_parts.append(f"[Source: {source}]\\n{doc.page_content}\\n")

    retrieved_context = "\\n---\\n".join(context_parts)

    print(f"Retrieved {len(results)} relevant documents")

    return {"retrieved_context": retrieved_context}

def load_memories(state: TestCaseState) -> TestCaseState:
    """Load STM (from state) and LTM (from ChromaDB) before generation."""
    requirement = state.get("requirement", "")
    conversation_history = state.get("conversation_history", [])

    # STM is already in state — restored automatically by MemorySaver
    print(f"Loaded conversation history: {len(conversation_history)} message(s)")

    # LTM — semantic search for past test patterns
    past_patterns = persistent_memory.get_context(
        query=f"test case patterns for {requirement[:100]}",
        top_k=3
    )

    return {"past_patterns": past_patterns}