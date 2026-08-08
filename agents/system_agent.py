import os
import subprocess
from agents.base_agent import BaseAgent

class SystemAgent(BaseAgent):
    name = "SystemAgent"
    description = "Specialized in local OS automation (file/folder management, running shell scripts, and web searching)."

    def execute(self, task: str) -> str:
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
            OPEN_FILE_EXPLORER_TOOL, open_file_explorer, 
            SEARCH_INTERNET_TOOL, search_internet,
            SWITCH_VOICE_PROFILE_TOOL, switch_voice_profile
        )
        from core.system_tools import (
            CHECK_SYSTEM_HEALTH_TOOL, check_system_health,
            LAUNCH_APP_TOOL, launch_app,
            DELETE_FILE_TOOL, delete_file
        )

        def _launch_app_wrapper(app_name: str):
            if getattr(self, 'approval_manager', None) and not self.approval_manager.require_approval(f"Launch Application: {app_name}"):
                return f"[{self.name}] Action aborted by user."
            return launch_app(app_name)

        def _delete_file_wrapper(file_path: str):
            if getattr(self, 'approval_manager', None) and not self.approval_manager.require_approval(f"Delete File: {file_path}"):
                return f"[{self.name}] Action aborted by user."
            return delete_file(file_path)
        
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
            tool_logic={
                "open_file_explorer": open_file_explorer,
                "check_system_health": check_system_health,
                "launch_app": _launch_app_wrapper,
                "search_internet": search_internet,
                "delete_file": _delete_file_wrapper,
                "switch_voice_profile": switch_voice_profile
            }
        )
        
        if not response:
            return f"[{self.name} ERROR]: Failed to generate response."

        self.memory.save_interaction(
            user_input=task, 
            ai_response=response, 
            activity_type=f"agent_execution_{self.name}"
        )
        return response
