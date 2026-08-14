import os
import subprocess
import signal
import socket
import time
from pathlib import Path
from agents.base_agent import BaseAgent
from core.verification import ToolResult, VerificationStatus

# Module-level process registry so start/stop can share state
_RUNNING_SERVERS: dict[str, subprocess.Popen] = {}

# Default configuration — paths are relative to the project root (e:\AI\Jarvis)
JARVIS_UI_DIR = str(Path(__file__).resolve().parent.parent / "jarvis-ui")
VITE_PORT = 5173


def _is_port_in_use(port: int) -> bool:
    """Returns True if a process is already listening on the given port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


class DevAgent(BaseAgent):
    name = "DevAgent"
    description = (
        "Specialized in coding tasks, inspecting local code directories, "
        "starting/stopping local dev servers (Vite React frontend), and reviewing code files."
    )

    def execute(self, task: str, task_id: str = None) -> str:
        """
        Uses LLM Tool Calling to autonomously start/stop servers or inspect directories.
        """
        print(f"\n[{self.name}] Analyzing development task...")
        
        # Define schemas for DevAgent's specific tools
        START_SERVER_TOOL = {
            "type": "function",
            "function": {
                "name": "start_server",
                "description": "Starts the Vite React frontend development server for jarvis-ui. Use this when the user asks to 'start server' or 'start dev server'.",
                "parameters": {"type": "object", "properties": {}}
            }
        }
        STOP_SERVER_TOOL = {
            "type": "function",
            "function": {
                "name": "stop_server",
                "description": "Stops the running Vite React frontend development server. Use this when the user asks to 'stop server'.",
                "parameters": {"type": "object", "properties": {}}
            }
        }
        SERVER_STATUS_TOOL = {
            "type": "function",
            "function": {
                "name": "server_status",
                "description": "Checks if the development server is currently running.",
                "parameters": {"type": "object", "properties": {}}
            }
        }
        INSPECT_DIR_TOOL = {
            "type": "function",
            "function": {
                "name": "inspect_directory",
                "description": "Lists all files in the current working directory.",
                "parameters": {"type": "object", "properties": {}}
            }
        }
        
        from core.tools import (
            SEARCH_INTERNET_TOOL, OPEN_URL_TOOL, OPEN_FILE_EXPLORER_TOOL, 
            OPEN_SYSTEM_SETTINGS_TOOL, PLAY_MEDIA_TOOL
        )
        from core.dev_tools import (
            read_code_file, write_code_file, READ_CODE_FILE_TOOL, WRITE_CODE_FILE_TOOL
        )
        from core.execution_gate import ToolMetadata, RiskLevel
        
        gate = self._setup_execution_gate(task_id)
        gate.register(ToolMetadata("start_server", RiskLevel.REVERSIBLE, "server_execution"), self._start_server)
        gate.register(ToolMetadata("stop_server", RiskLevel.REVERSIBLE, "server_execution"), self._stop_server)
        gate.register(ToolMetadata("server_status", RiskLevel.READ_ONLY, "process_monitoring"), self._server_status)
        gate.register(ToolMetadata("inspect_directory", RiskLevel.READ_ONLY, "fs_read"), self._inspect_directory)
        gate.register(ToolMetadata("read_code_file", RiskLevel.READ_ONLY, "fs_read"), read_code_file)
        gate.register(ToolMetadata("write_code_file", RiskLevel.REVERSIBLE, "fs_write"), write_code_file)
        
        system_prompt = (
            f"You are {self.name}. {self.description}\n"
            "You can converse naturally in English, Urdu, and Punjabi, but YOU MUST DEFAULT TO ENGLISH. "
            "CRITICAL RULE: If the user types in English (e.g., 'Hello', 'Hi'), YOU MUST REPLY IN ENGLISH. ONLY use Urdu or Punjabi if the user explicitly writes in those languages (e.g., 'kya haal hai', 'کیا حال ہے'). "
            "Use your tools to perform actions on the local development environment. "
            "CRITICAL RULE: DO NOT use any tools for simple greetings or casual chit-chat. Only use tools when explicitly asked to perform an action on the computer. Never describe manual steps."
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
            
        response = self.llm.generate_response(
            prompt=task,
            system_prompt=system_prompt,
            tools=[
                START_SERVER_TOOL, STOP_SERVER_TOOL, SERVER_STATUS_TOOL, INSPECT_DIR_TOOL,
                READ_CODE_FILE_TOOL, WRITE_CODE_FILE_TOOL,
                SEARCH_INTERNET_TOOL, OPEN_URL_TOOL, OPEN_FILE_EXPLORER_TOOL, 
                OPEN_SYSTEM_SETTINGS_TOOL, PLAY_MEDIA_TOOL
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

    # ─────────────────────────────────────────────────────────────────────────
    # Tool: Inspect Directory
    # ─────────────────────────────────────────────────────────────────────────

    def _inspect_directory(self) -> ToolResult:
        """Lists files in the current working directory."""
        try:
            files = os.listdir(".")
            result = f"Current directory contents ({len(files)} items): {', '.join(files)}"
            self.memory.save_interaction(
                user_input="Inspect Directory",
                ai_response=result,
                activity_type="dev_agent_tool",
            )
            return ToolResult(
                status=VerificationStatus.VERIFIED_SUCCESS,
                message=result,
                evidence="os.listdir returned successfully."
            )
        except Exception as e:
            return ToolResult(
                status=VerificationStatus.VERIFIED_FAILURE,
                message=f"[{self.name} ERROR] Failed to inspect directory: {e}",
                evidence="Exception raised during os.listdir."
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Tool: Start Server (Vite React Frontend via `npm run dev`)
    # ─────────────────────────────────────────────────────────────────────────

    def _start_server(self) -> ToolResult:
        """
        Starts the Vite dev server for jarvis-ui using `npm run dev`.
        Handles: already-running processes, port conflicts, missing npm.
        """
        server_key = "jarvis-ui"

        # ── Guard: process already tracked ──────────────────────────────────
        if server_key in _RUNNING_SERVERS:
            proc = _RUNNING_SERVERS[server_key]
            if proc.poll() is None:  # still running
                return ToolResult(
                    status=VerificationStatus.VERIFIED_SUCCESS,
                    message=f"[{self.name}] Server '{server_key}' is already running (PID {proc.pid}). Use 'stop server' to terminate it first.",
                    evidence=f"Process {proc.pid} is alive."
                )
            else:
                # Process died on its own — clean up stale entry
                del _RUNNING_SERVERS[server_key]

        # ── Guard: port already occupied by another process ──────────────────
        if _is_port_in_use(VITE_PORT):
            return ToolResult(
                status=VerificationStatus.VERIFIED_FAILURE,
                message=f"[{self.name}] Port {VITE_PORT} is already in use by another process. Stop that process manually or use a different port.",
                evidence=f"_is_port_in_use({VITE_PORT}) returned True before starting."
            )

        # ── Guard: ui directory must exist ───────────────────────────────────
        if not os.path.isdir(JARVIS_UI_DIR):
            return ToolResult(
                status=VerificationStatus.VERIFIED_FAILURE,
                message=f"[{self.name} ERROR] jarvis-ui directory not found at: {JARVIS_UI_DIR}. Cannot start server.",
                evidence=f"os.path.isdir({JARVIS_UI_DIR}) returned False."
            )

        try:
            print(f"[{self.name}] Launching 'npm run dev' in {JARVIS_UI_DIR} ...")
            proc = subprocess.Popen(
                ["npm", "run", "dev"],
                cwd=JARVIS_UI_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
                text=True,
            )
            _RUNNING_SERVERS[server_key] = proc

            # Polling for verification
            max_attempts = 10
            attempt = 0
            while attempt < max_attempts:
                time.sleep(1)
                
                # Check if process died
                if proc.poll() is not None:
                    _, stderr = proc.communicate()
                    del _RUNNING_SERVERS[server_key]
                    return ToolResult(
                        status=VerificationStatus.VERIFIED_FAILURE,
                        message=f"[{self.name} ERROR] Server process exited unexpectedly.",
                        evidence=f"Exit code: {proc.returncode}. Stderr: {stderr[:500]}"
                    )
                
                # Verify port is open
                if _is_port_in_use(VITE_PORT):
                    result_msg = f"✅ Vite dev server started successfully (PID {proc.pid}). Open http://localhost:{VITE_PORT} in your browser."
                    self.memory.save_interaction(user_input="Start Server", ai_response=result_msg, activity_type="dev_agent_tool")
                    return ToolResult(
                        status=VerificationStatus.VERIFIED_SUCCESS,
                        message=result_msg,
                        evidence=f"_is_port_in_use({VITE_PORT}) returned True."
                    )
                
                attempt += 1

            # If we exit the loop, port never opened
            proc.kill()
            del _RUNNING_SERVERS[server_key]
            return ToolResult(
                status=VerificationStatus.VERIFIED_FAILURE,
                message=f"[{self.name} ERROR] Server process started (PID {proc.pid}) but port {VITE_PORT} did not open within {max_attempts} seconds.",
                evidence=f"_is_port_in_use({VITE_PORT}) returned False consistently."
            )

        except FileNotFoundError:
            return ToolResult(
                status=VerificationStatus.VERIFIED_FAILURE,
                message=f"[{self.name} ERROR] 'npm' command not found. Make sure Node.js is installed and available on your PATH.",
                evidence="FileNotFoundError raised when invoking 'npm'."
            )
        except Exception as e:
            return ToolResult(
                status=VerificationStatus.VERIFIED_FAILURE,
                message=f"[{self.name} ERROR] Failed to start server: {e}",
                evidence="Exception raised during process launch."
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Tool: Stop Server
    # ─────────────────────────────────────────────────────────────────────────

    def _stop_server(self) -> ToolResult:
        """
        Terminates the tracked Vite dev server process gracefully,
        with a force-kill fallback for Windows.
        """
        server_key = "jarvis-ui"

        if server_key not in _RUNNING_SERVERS:
            # No tracked process — check if port is still in use
            if _is_port_in_use(VITE_PORT):
                return ToolResult(
                    status=VerificationStatus.VERIFIED_FAILURE,
                    message=f"[{self.name}] No server was started by this session, but port {VITE_PORT} is in use by an external process. You'll need to stop it manually.",
                    evidence=f"_is_port_in_use({VITE_PORT}) returned True, but not in _RUNNING_SERVERS."
                )
            return ToolResult(
                status=VerificationStatus.VERIFIED_SUCCESS,
                message=f"[{self.name}] No running server to stop.",
                evidence=f"Not in _RUNNING_SERVERS and port {VITE_PORT} is not in use."
            )

        proc = _RUNNING_SERVERS[server_key]
        try:
            if proc.poll() is None:  # still running
                if os.name == "nt":
                    # On Windows, send CTRL_BREAK_EVENT to the process group
                    proc.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    proc.terminate()  # SIGTERM on Unix

                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print(f"[{self.name}] Graceful shutdown timed out. Force killing...")
                    proc.kill()
                    proc.wait()

            del _RUNNING_SERVERS[server_key]
            
            # Verify port is closed
            if _is_port_in_use(VITE_PORT):
                return ToolResult(
                    status=VerificationStatus.VERIFIED_FAILURE,
                    message=f"[{self.name} ERROR] Process was killed but port {VITE_PORT} is still in use.",
                    evidence=f"_is_port_in_use({VITE_PORT}) returned True."
                )

            result = f"✅ Vite dev server (PID {proc.pid}) stopped successfully."
            self.memory.save_interaction(user_input="Stop Server", ai_response=result, activity_type="dev_agent_tool")
            return ToolResult(
                status=VerificationStatus.VERIFIED_SUCCESS,
                message=result,
                evidence=f"Process exited and _is_port_in_use({VITE_PORT}) returned False."
            )

        except Exception as e:
            return ToolResult(
                status=VerificationStatus.VERIFIED_FAILURE,
                message=f"[{self.name} ERROR] Failed to stop server: {e}",
                evidence="Exception raised during process termination."
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Tool: Server Status
    # ─────────────────────────────────────────────────────────────────────────

    def _server_status(self) -> ToolResult:
        """Reports whether the tracked server process and port are active."""
        server_key = "jarvis-ui"
        port_live = _is_port_in_use(VITE_PORT)
        tracked = server_key in _RUNNING_SERVERS
        pid_info = ""

        if tracked:
            proc = _RUNNING_SERVERS[server_key]
            alive = proc.poll() is None
            pid_info = f", PID {proc.pid}, process {'alive' if alive else 'dead'}"

        msg = (
            f"[{self.name}] Server Status:\n"
            f"  • Tracked by JARVIS : {'Yes' + pid_info if tracked else 'No'}\n"
            f"  • Port {VITE_PORT} in use   : {'Yes ✅' if port_live else 'No ❌'}\n"
            f"  • URL               : http://localhost:{VITE_PORT}"
        )
        return ToolResult(
            status=VerificationStatus.VERIFIED_SUCCESS,
            message=msg,
            evidence=f"Tracked: {tracked}, Port Live: {port_live}."
        )
