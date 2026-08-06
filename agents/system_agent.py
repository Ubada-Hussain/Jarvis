import os
import subprocess
from agents.base_agent import BaseAgent

class SystemAgent(BaseAgent):
    name = "SystemAgent"
    description = "Specialized in local OS automation (file/folder management, running shell scripts, and web searching)."

    def execute(self, task: str) -> str:
        """
        Executes system level tasks. Relies on the BaseAgent tool calling 
        capabilities to perform web searches autonomously.
        """
        print(f"\n[{self.name}] Analyzing system task...")
        return super().execute(task)
