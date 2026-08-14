import os
import subprocess
from agents.base_agent import BaseAgent

class SystemAgent(BaseAgent):
    name = "SystemAgent"
    description = "Specialized in local OS automation (file/folder management, running shell scripts, and web searching)."

    def execute(self, task: str, task_id: str = None) -> str:
        """
        Executes system level tasks. Uses specific OS tools for health, launching apps, and file explorer.
        """
        print(f"\n[{self.name}] Analyzing system task...")
        
        system_prompt = (
            f"You are {self.name}. {self.description}\n"
            "You can converse naturally in English, Urdu, and Punjabi, but YOU MUST DEFAULT TO ENGLISH. "
            "CRITICAL RULE: If the user types in English (e.g., 'Hello', 'Hi'), YOU MUST REPLY IN ENGLISH. ONLY use Urdu or Punjabi if the user explicitly writes in those languages (e.g., 'kya haal hai', 'کیا حال ہے'). "
            "CRITICAL RULE: DO NOT use any tools for simple greetings or casual chit-chat. Only use tools when explicitly asked to perform an action on the computer like open an app, check RAM/CPU, or open a folder. Never describe manual steps."
        )

        from core.tools import (
            OPEN_FILE_EXPLORER_TOOL, 
            SEARCH_INTERNET_TOOL,
            SWITCH_VOICE_PROFILE_TOOL, switch_voice_profile
        )
        from core.system_tools import (
            CHECK_SYSTEM_HEALTH_TOOL, check_system_health,
            LAUNCH_APP_TOOL, launch_app,
            DELETE_FILE_TOOL, delete_file
        )

        from core.execution_gate import ToolMetadata, RiskLevel
        
        gate = self._setup_execution_gate(task_id)
        gate.register(ToolMetadata("check_system_health", RiskLevel.READ_ONLY, "system_read"), check_system_health)
        gate.register(ToolMetadata("launch_app", RiskLevel.REVERSIBLE, "process_execution"), launch_app)
        gate.register(ToolMetadata("delete_file", RiskLevel.DESTRUCTIVE, "fs_write", requires_confirmation=True), delete_file)
        gate.register(ToolMetadata("switch_voice_profile", RiskLevel.REVERSIBLE, "config_write"), switch_voice_profile)

        response = self.llm.generate_response(
            prompt=task, 
            system_prompt=system_prompt,
            tools=[
                OPEN_FILE_EXPLORER_TOOL,
                CHECK_SYSTEM_HEALTH_TOOL,
                LAUNCH_APP_TOOL,
                SEARCH_INTERNET_TOOL,
                DELETE_FILE_TOOL,
                SWITCH_VOICE_PROFILE_TOOL
            ],
            tool_logic=gate
        )
        
        if not response:
            return f"[{self.name} ERROR]: Failed to generate response."

        self.memory.save_interaction(
            user_input=task, 
            ai_response=response, 
            activity_type=f"agent_execution_{self.name}"
        )
        return response
