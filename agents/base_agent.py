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

    def _setup_execution_gate(self, task_id: str = None) -> "ExecutionGate":
        """Instantiates the ExecutionGate and registers default tools."""
        from core.execution_gate import ExecutionGate, ToolMetadata, RiskLevel
        from core.system_tools import (
            create_procedure, CREATE_PROCEDURE_TOOL,
            refresh_environment_index, REFRESH_ENV_TOOL,
            query_environment_index, QUERY_ENV_TOOL
        )
        from core.tools import (
            search_internet, open_url, open_file_explorer, 
            open_system_settings, play_media, remember_file
        )
        
        gate = ExecutionGate(self.approval_manager, agent_name=self.name, task_id=task_id)
        
        gate.register(ToolMetadata("search_internet", RiskLevel.READ_ONLY, "network_access"), search_internet)
        gate.register(ToolMetadata("open_url", RiskLevel.REVERSIBLE, "browser_access"), open_url)
        gate.register(ToolMetadata("open_file_explorer", RiskLevel.REVERSIBLE, "system_access"), open_file_explorer)
        gate.register(ToolMetadata("open_system_settings", RiskLevel.REVERSIBLE, "system_access"), open_system_settings)
        gate.register(ToolMetadata("play_media", RiskLevel.REVERSIBLE, "browser_access"), play_media)
        gate.register(ToolMetadata("remember_file", RiskLevel.REVERSIBLE, "db_write"), remember_file)
        gate.register(ToolMetadata("create_procedure", RiskLevel.REVERSIBLE, "db_write"), create_procedure)
        gate.register(ToolMetadata("refresh_environment_index", RiskLevel.READ_ONLY, "fs_read"), refresh_environment_index)
        gate.register(ToolMetadata("query_environment_index", RiskLevel.READ_ONLY, "db_read"), query_environment_index)
        
        return gate

    def execute(self, task: str, task_id: str = None) -> str:
        """
        Executes a task using the agent's persona. Subclasses can override this 
        to add custom logic or tool usage before relying on the LLM.
        """
        print(f"\n[{self.name}] Thinking...")
        system_prompt = (
            f"You are JARVIS ({self.name}). {self.description}\n"
            "Keep responses brief, crisp, confident, and slightly witty (Iron Man style). "
            "1-3 sentences typically. ONLY provide long answers if a detailed report/explanation is specifically requested. "
            "Avoid formal, corporate AI assistant language entirely.\n"
            "You can converse naturally in English, Urdu, and Punjabi, but YOU MUST DEFAULT TO ENGLISH. "
            "CRITICAL RULE: If the user types in English, YOU MUST REPLY IN ENGLISH. ONLY use Urdu or Punjabi if the user explicitly writes in those languages. "
            "CRITICAL RULE: DO NOT use any tools for simple greetings, casual chit-chat, or general questions that don't require external actions."
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
            SEARCH_INTERNET_TOOL, OPEN_URL_TOOL, OPEN_FILE_EXPLORER_TOOL,
            OPEN_SYSTEM_SETTINGS_TOOL, PLAY_MEDIA_TOOL, REMEMBER_FILE_TOOL
        )
        from core.system_tools import (
            CREATE_PROCEDURE_TOOL,
            REFRESH_ENV_TOOL,
            QUERY_ENV_TOOL
        )
        
        gate = self._setup_execution_gate(task_id)
        
        response = self.llm.generate_response(
            prompt=task, 
            system_prompt=system_prompt,
            tools=[
                SEARCH_INTERNET_TOOL, 
                OPEN_URL_TOOL, 
                OPEN_FILE_EXPLORER_TOOL,
                OPEN_SYSTEM_SETTINGS_TOOL,
                PLAY_MEDIA_TOOL,
                REMEMBER_FILE_TOOL,
                CREATE_PROCEDURE_TOOL,
                REFRESH_ENV_TOOL,
                QUERY_ENV_TOOL
            ],
            tool_logic=gate
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
