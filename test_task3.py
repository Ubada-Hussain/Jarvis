import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from core.llm_engine import LLMEngine
from core.memory_manager import MemoryManager
from agents.system_agent import SystemAgent
from agents.master_agent import MasterAgent

def main():
    llm = LLMEngine()
    memory = MemoryManager()
    
    # We can use SystemAgent directly to avoid MasterAgent routing to DevAgent again
    agent = SystemAgent(llm, memory)

    q1 = "open calculator for me"
    print(f"\nTask: {q1}")
    res1 = agent.execute(q1)
    print(f"Response: {res1}")

    q2 = "check system RAM and CPU usage"
    print(f"\nTask: {q2}")
    res2 = agent.execute(q2)
    print(f"Response: {res2}")

if __name__ == '__main__':
    main()
