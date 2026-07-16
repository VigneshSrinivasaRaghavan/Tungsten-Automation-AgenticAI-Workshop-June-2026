from langgraph.graph import StateGraph, END
from .state import TestCaseState
from .nodes import read_requirement, generate_tests, save_outputs, retry_generate, route_after_validation, validate_tests, route_after_human_approval, show_preview, human_approval, retrieve_context, load_memories
from langgraph.checkpoint.memory import MemorySaver

def build_graph():
    # Create a graph
    workflow = StateGraph(TestCaseState)
    
    # Add nodes
    workflow.add_node("read",read_requirement)
    workflow.add_node("retrieve",retrieve_context)
    workflow.add_node("generate",generate_tests)
    workflow.add_node("save",save_outputs)
    workflow.add_node("retry",retry_generate)
    workflow.add_node("validate",validate_tests)
    workflow.add_node("route",route_after_validation)
    workflow.add_node("preview",show_preview)
    workflow.add_node("approval",human_approval)
    workflow.add_node("load_memories",load_memories)
    
    # Connect nodes
    workflow.set_entry_point("read")
    workflow.add_edge("read", "retrieve")
    workflow.add_edge("retrieve", "load_memories")
    workflow.add_edge("load_memories", "generate")
    workflow.add_edge("generate", "validate")
    
    workflow.add_conditional_edges(
        "validate",
        route_after_validation,
        {
            "preview": "preview",
            "retry": "retry"
        }
    )
    
    workflow.add_edge("preview", "approval")
    
    workflow.add_conditional_edges(
        "approval",
        route_after_human_approval,
        {
            "save": "save",
            "retry": "retry"
        }
    )
    
    workflow.add_edge("retry", "validate")
    
    workflow.add_edge("save", END)
    
    # Compile graph
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)