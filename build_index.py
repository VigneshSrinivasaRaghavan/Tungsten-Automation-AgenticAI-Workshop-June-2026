"""
Build vector store from knowledge base documents
Run this once to create the index
"""
from src.core import build_vector_store


if __name__ == "__main__":
    print("Building vector store from knowledge base...")

    try:
        vector_store = build_vector_store()

        print("Vector store built successfully!")
        print("Running test search...")

        # # Test search
        # results = vector_store.similarity_search("how to test login API", k=2)

        # for i, doc in enumerate(results, 1):
        #     source = doc.metadata.get('source', 'Unknown')
        #     print(f"[{i}] {source}")
        #     print(f"    {doc.page_content[:150]}...")

    except Exception as e:
        print(f"Error: {e}")
