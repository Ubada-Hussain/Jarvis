import asyncio
from core.llm_engine import LLMEngine
from core.memory_manager import MemoryManager
from agents.master_agent import MasterAgent

def main():
    print("Initializing components...")
    llm = LLMEngine()
    memory = MemoryManager()
    master = MasterAgent(llm, memory)

    print("\nSending command: 'open youtube'")
    response = master.execute("open youtube")
    print(f"\nFinal Response: {response}")

if __name__ == '__main__':
    main()
