from core.llm_engine import LLMEngine
from core.memory_manager import MemoryManager

class BaseAgent:
    """
    The foundational agent class that connects to the LLM and Memory.
    All sub-agents must inherit from this class.
    """
    name = "BaseAgent"
    description = "A basic generic agent."
    
    def __init__(self, llm: LLMEngine, memory: MemoryManager, approval_manager=None):
        self.llm = llm
        self.memory = memory
        self.approval_manager = approval_manager

    def execute(self, task: str) -> str:
        """
        Executes a task using the agent's persona. Subclasses can override this 
        to add custom logic or tool usage before relying on the LLM.
        """
        print(f"\n[{self.name}] Thinking...")
        system_prompt = f"You are {self.name}. {self.description}\nProvide concise and accurate answers."
        
        response = self.llm.generate_response(prompt=task, system_prompt=system_prompt)
        
        if not response:
            return f"[{self.name} ERROR]: Failed to generate response."

        # Log execution to memory
        self.memory.save_interaction(
            user_input=task, 
            ai_response=response, 
            activity_type=f"agent_execution_{self.name}"
        )
        return response
