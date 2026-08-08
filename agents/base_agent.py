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
        system_prompt = (
            f"You are {self.name}. {self.description}\n"
            "Provide concise and accurate answers. "
            "You can converse naturally in English, Urdu, and Punjabi, but YOU MUST DEFAULT TO ENGLISH. "
            "CRITICAL RULE: If the user types in English (e.g., 'Hello', 'Hi'), YOU MUST REPLY IN ENGLISH. ONLY use Urdu or Punjabi if the user explicitly writes in those languages (e.g., 'kya haal hai', 'کیا حال ہے'). "
            "CRITICAL RULE: DO NOT use any tools for simple greetings, casual chit-chat, or general questions that don't require external actions. Only use tools when explicitly asked to perform an action on the computer (like open a website, play a song, open settings, or open a file explorer). Never describe manual steps for actions you have a tool for."
        )
        
        # --- RAG / Memory Injection ---
        try:
            relevant_chunks = self.memory.get_relevant_context(task, max_results=3)
            if relevant_chunks:
                system_prompt += "\n\n<MEMORY_CONTEXT>\n"
                for chunk in relevant_chunks:
                    system_prompt += f"- {chunk}\n"
                system_prompt += "</MEMORY_CONTEXT>\n"
        except Exception as e:
            print(f"[RAG WARNING] Failed to retrieve context: {e}")

        
        from core.tools import (
            SEARCH_INTERNET_TOOL, search_internet,
            OPEN_URL_TOOL, open_url,
            OPEN_FILE_EXPLORER_TOOL, open_file_explorer,
            OPEN_SYSTEM_SETTINGS_TOOL, open_system_settings,
            PLAY_MEDIA_TOOL, play_media,
            REMEMBER_FILE_TOOL, remember_file
        )
        response = self.llm.generate_response(
            prompt=task, 
            system_prompt=system_prompt,
            tools=[
                SEARCH_INTERNET_TOOL, 
                OPEN_URL_TOOL, 
                OPEN_FILE_EXPLORER_TOOL,
                OPEN_SYSTEM_SETTINGS_TOOL,
                PLAY_MEDIA_TOOL,
                REMEMBER_FILE_TOOL
            ],
            tool_logic={
                "search_internet": search_internet,
                "open_url": open_url,
                "open_file_explorer": open_file_explorer,
                "open_system_settings": open_system_settings,
                "play_media": play_media,
                "remember_file": remember_file
            }
        )
        
        if not response:
            return f"[{self.name} ERROR]: Failed to generate response."

        # Log execution to memory
        self.memory.save_interaction(
            user_input=task, 
            ai_response=response, 
            activity_type=f"agent_execution_{self.name}"
        )
        return response
