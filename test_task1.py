import os
from core.llm_engine import LLMEngine
from core.memory_manager import MemoryManager
from agents.master_agent import MasterAgent
from core.rag_ingestion import ingest_file_to_chroma

def main():
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    llm = LLMEngine()
    memory = MemoryManager()
    master = MasterAgent(llm, memory)

    question = "Based ONLY on the memory context provided, what is the favorite color of Project Obsidian's mascot?"

    print("=== BEFORE INGESTION ===")
    res_before = master.execute(question)
    print(f"\nResponse Before: {res_before}\n")

    print("=== INGESTING FILE ===")
    test_file = "test.txt"
    try:
        msg = ingest_file_to_chroma(test_file, memory.long_term)
        print(msg)
    except Exception as e:
        print(f"Ingestion failed: {e}")

    print("\n=== AFTER INGESTION ===")
    res_after = master.execute(question)
    print(f"\nResponse After: {res_after}\n")

if __name__ == "__main__":
    main()
