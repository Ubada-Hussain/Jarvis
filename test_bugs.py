import sys
import io

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from agents.master_agent import MasterAgent
from core.llm_engine import LLMEngine
from core.memory_manager import MemoryManager

def test_bugs():
    llm = LLMEngine()
    memory = MemoryManager()
    master = MasterAgent(llm, memory)
    
    print("\n--- TEST 1: Language Consistency ('Hello Hello Hello Hello') ---")
    response1 = master.execute("Hello Hello Hello Hello")
    print(f"\nResponse 1: {response1}")
    
    print("\n--- TEST 2: No Tool Calling on Greeting ('Hello Jarvis') ---")
    response2 = master.execute("Hello Jarvis")
    print(f"\nResponse 2: {response2}")

if __name__ == "__main__":
    test_bugs()
