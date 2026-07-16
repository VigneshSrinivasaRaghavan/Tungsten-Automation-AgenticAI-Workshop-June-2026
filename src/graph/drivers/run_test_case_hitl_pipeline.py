from src.graph.test_case_generator_hitl.graph import build_graph

def main():
    print("🚀 Starting TestCase Generator pipeline...")
    
    # Build graph
    app = build_graph()
    
    # Initialize empty state
    init_state = {
        "requirement": "",
        "retrieved_context": "",
        "test_cases": [],
        "errors": [],
        "validation_status": "pending",
        "retry_count": 0,
        "human_approval": "pending",
        "human_feedback": ""
    }
    
    # Run Graph
    final_state = app.invoke(init_state)
    
    # Show results
    print(f"✅ Pipeline complete!")
    print(f"Generated {len(final_state.get('test_cases', []))} test cases")
    print(f"Validation: {final_state.get('validation_status', 'unknown')}")
    print(f"Retries: {final_state.get('retry_count', 0)}")
    
    if final_state.get('human_feedback'):
        print(f"Human Feedback: {final_state['human_feedback']}")
    
    if final_state.get('errors'):
        print(f"Errors: {final_state['errors']}")

if __name__ == "__main__":
    main()