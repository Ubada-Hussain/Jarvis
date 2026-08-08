import os
from core.llm_engine import LLMEngine
from core.memory_manager import MemoryManager
from agents.academic_agent import AcademicAgent

def main():
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    llm = LLMEngine()
    memory = MemoryManager()
    agent = AcademicAgent(llm, memory)

    question = "Can you check the web and tell me what is the date today?"
    print(f"Sending question: {question}")
    
    response = agent.execute(question)
    print(f"\nResponse: {response}")

if __name__ == '__main__':
    main()
