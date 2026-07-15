from src.graph.test_case_generator_rag.graph import build_graph

def main():
    print("Running test case generation pipeline...")
    
    # Build the graph
    app = build_graph()

    # Initialize the emtpy state
    init_state = {
        "requirement": "",
        "retrieved_context": "",
        "test_cases": [],
        "errors": []
    }

    # Run Pipeline
    final_state = app.invoke(init_state)

    # Show results
    print("\nPipeline completed.")
    print(f"Generated {len(final_state.get('test_cases', []))} test cases")

if __name__ == "__main__":
    main()