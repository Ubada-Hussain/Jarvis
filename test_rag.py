from core.memory_manager import MemoryManager

def main():
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    memory = MemoryManager()
    question = "Project Obsidian's mascot favorite color"
    
    print(f"Querying ChromaDB for: '{question}'")
    results = memory.get_relevant_context(question, max_results=10)
    
    print("\n[RAG RETRIEVAL RESULTS]")
    if results:
        for i, res in enumerate(results, 1):
            print(f"Result {i}: {res}")
    else:
        print("No results found.")

if __name__ == '__main__':
    main()
