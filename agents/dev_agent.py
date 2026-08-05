import os
import subprocess
from agents.base_agent import BaseAgent

class DevAgent(BaseAgent):
    name = "DevAgent"
    description = "Specialized in coding tasks, inspecting local code directories, starting/stopping local servers, and reviewing code files."

    def execute(self, task: str) -> str:
        """
        Custom execution loop that checks if the task requires OS tools,
        otherwise falls back to standard LLM processing.
        """
        print(f"\n[{self.name}] Analyzing development task...")
        
        # A simple keyword heuristic to trigger local dev tools
        # In a more advanced version, this would be an LLM-driven tool selection loop.
        if "list files" in task.lower() or "inspect directory" in task.lower():
            return self._inspect_directory()
        elif "start server" in task.lower():
            return self._start_server()
        elif "stop server" in task.lower():
            return self._stop_server()
            
        # Fallback to LLM for coding advice or code generation
        return super().execute(task)

    def _inspect_directory(self) -> str:
        """Lists files in the current directory."""
        try:
            files = os.listdir('.')
            result = f"Current directory contents: {', '.join(files)}"
            # Optionally log this execution explicitly
            self.memory.save_interaction(user_input="Inspect Directory", ai_response=result, activity_type="dev_agent_tool")
            return result
        except Exception as e:
            return f"[{self.name} ERROR] Failed to inspect directory: {e}"

    def _start_server(self) -> str:
        """Mock function to start a local server."""
        if self.approval_manager and not self.approval_manager.require_approval("Start local development server"):
            return f"[{self.name}] Action aborted by user."

        # For security, we just mock this. A real implementation would use subprocess.Popen
        # e.g., subprocess.Popen(['npm', 'start'])
        result = "Mock: Started local development server."
        self.memory.save_interaction(user_input="Start Server", ai_response=result, activity_type="dev_agent_tool")
        return result

    def _stop_server(self) -> str:
        """Mock function to stop a local server."""
        if self.approval_manager and not self.approval_manager.require_approval("Stop local development server"):
            return f"[{self.name}] Action aborted by user."

        result = "Mock: Stopped local development server."
        self.memory.save_interaction(user_input="Stop Server", ai_response=result, activity_type="dev_agent_tool")
        return result
