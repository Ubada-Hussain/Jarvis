import os
import subprocess
import signal
import socket
from pathlib import Path
from agents.base_agent import BaseAgent

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

    def execute(self, task: str) -> str:
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
            SEARCH_INTERNET_TOOL, search_internet, 
            OPEN_URL_TOOL, open_url, 
            OPEN_FILE_EXPLORER_TOOL, open_file_explorer,
            OPEN_SYSTEM_SETTINGS_TOOL, open_system_settings,
            PLAY_MEDIA_TOOL, play_media
        )
        
        system_prompt = (
            f"You are {self.name}. {self.description}\n"
            "You can converse naturally in English, Urdu, and Punjabi. "
            "CRITICAL RULE: Always reply in the same language the user speaks to you (e.g., if they speak Urdu, reply in Urdu using the native script like 'کیا حال ہے'). "
            "Use your tools to perform actions on the local development environment. "
            "CRITICAL RULE: If the user asks you to DO something, you MUST call the matching tool. Never describe manual steps."
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
                SEARCH_INTERNET_TOOL, OPEN_URL_TOOL, OPEN_FILE_EXPLORER_TOOL, 
                OPEN_SYSTEM_SETTINGS_TOOL, PLAY_MEDIA_TOOL
            ],
            tool_logic={
                "start_server": self._start_server,
                "stop_server": self._stop_server,
                "server_status": self._server_status,
                "inspect_directory": self._inspect_directory,
                "search_internet": search_internet,
                "open_url": open_url,
                "open_file_explorer": open_file_explorer,
                "open_system_settings": open_system_settings,
                "play_media": play_media
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

    # ─────────────────────────────────────────────────────────────────────────
    # Tool: Inspect Directory
    # ─────────────────────────────────────────────────────────────────────────

    def _inspect_directory(self) -> str:
        """Lists files in the current working directory."""
        try:
            files = os.listdir(".")
            result = f"Current directory contents ({len(files)} items): {', '.join(files)}"
            self.memory.save_interaction(
                user_input="Inspect Directory",
                ai_response=result,
                activity_type="dev_agent_tool",
            )
            return result
        except Exception as e:
            return f"[{self.name} ERROR] Failed to inspect directory: {e}"

    # ─────────────────────────────────────────────────────────────────────────
    # Tool: Start Server (Vite React Frontend via `npm run dev`)
    # ─────────────────────────────────────────────────────────────────────────

    def _start_server(self) -> str:
        """
        Starts the Vite dev server for jarvis-ui using `npm run dev`.
        Handles: already-running processes, port conflicts, missing npm.
        """
        server_key = "jarvis-ui"

        # ── Guard: process already tracked ──────────────────────────────────
        if server_key in _RUNNING_SERVERS:
            proc = _RUNNING_SERVERS[server_key]
            if proc.poll() is None:  # still running
                return (
                    f"[{self.name}] Server '{server_key}' is already running "
                    f"(PID {proc.pid}). Use 'stop server' to terminate it first."
                )
            else:
                # Process died on its own — clean up stale entry
                del _RUNNING_SERVERS[server_key]

        # ── Guard: port already occupied by another process ──────────────────
        if _is_port_in_use(VITE_PORT):
            return (
                f"[{self.name}] Port {VITE_PORT} is already in use by another process. "
                f"Stop that process manually or use a different port."
            )

        # ── Guard: ui directory must exist ───────────────────────────────────
        if not os.path.isdir(JARVIS_UI_DIR):
            return (
                f"[{self.name} ERROR] jarvis-ui directory not found at: {JARVIS_UI_DIR}. "
                "Cannot start server."
            )

        # ── Approval gate ─────────────────────────────────────────────────────
        if self.approval_manager and not self.approval_manager.require_approval(
            f"Start Vite dev server in {JARVIS_UI_DIR}"
        ):
            return f"[{self.name}] Action aborted by user."

        try:
            print(f"[{self.name}] Launching 'npm run dev' in {JARVIS_UI_DIR} ...")
            proc = subprocess.Popen(
                ["npm", "run", "dev"],
                cwd=JARVIS_UI_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                # On Windows, create a new process group so we can kill it cleanly
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
                text=True,
            )
            _RUNNING_SERVERS[server_key] = proc

            # Give Vite ~2 seconds to start, then verify the port is live
            import time
            time.sleep(2)
            if proc.poll() is not None:
                # Process already died — capture stderr for diagnostics
                _, stderr = proc.communicate()
                return (
                    f"[{self.name} ERROR] Server failed to start.\n"
                    f"Exit code: {proc.returncode}\n"
                    f"Stderr: {stderr[:500]}"
                )

            if _is_port_in_use(VITE_PORT):
                result = (
                    f"✅ Vite dev server started successfully (PID {proc.pid}). "
                    f"Open http://localhost:{VITE_PORT} in your browser."
                )
            else:
                result = (
                    f"⚠️ Server process started (PID {proc.pid}) but port {VITE_PORT} "
                    "is not yet responding. It may still be initializing."
                )

            self.memory.save_interaction(
                user_input="Start Server",
                ai_response=result,
                activity_type="dev_agent_tool",
            )
            return result

        except FileNotFoundError:
            return (
                f"[{self.name} ERROR] 'npm' command not found. "
                "Make sure Node.js is installed and available on your PATH."
            )
        except Exception as e:
            return f"[{self.name} ERROR] Failed to start server: {e}"

    # ─────────────────────────────────────────────────────────────────────────
    # Tool: Stop Server
    # ─────────────────────────────────────────────────────────────────────────

    def _stop_server(self) -> str:
        """
        Terminates the tracked Vite dev server process gracefully,
        with a force-kill fallback for Windows.
        """
        server_key = "jarvis-ui"

        if server_key not in _RUNNING_SERVERS:
            # No tracked process — check if port is still in use
            if _is_port_in_use(VITE_PORT):
                return (
                    f"[{self.name}] No server was started by this session, "
                    f"but port {VITE_PORT} is in use by an external process. "
                    "You'll need to stop it manually."
                )
            return f"[{self.name}] No running server to stop."

        # ── Approval gate ─────────────────────────────────────────────────────
        if self.approval_manager and not self.approval_manager.require_approval(
            "Stop Vite dev server"
        ):
            return f"[{self.name}] Action aborted by user."

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
            result = f"✅ Vite dev server (PID {proc.pid}) stopped successfully."
            self.memory.save_interaction(
                user_input="Stop Server",
                ai_response=result,
                activity_type="dev_agent_tool",
            )
            return result

        except Exception as e:
            return f"[{self.name} ERROR] Failed to stop server: {e}"

    # ─────────────────────────────────────────────────────────────────────────
    # Tool: Server Status
    # ─────────────────────────────────────────────────────────────────────────

    def _server_status(self) -> str:
        """Reports whether the tracked server process and port are active."""
        server_key = "jarvis-ui"
        port_live = _is_port_in_use(VITE_PORT)
        tracked = server_key in _RUNNING_SERVERS
        pid_info = ""

        if tracked:
            proc = _RUNNING_SERVERS[server_key]
            alive = proc.poll() is None
            pid_info = f", PID {proc.pid}, process {'alive' if alive else 'dead'}"

        return (
            f"[{self.name}] Server Status:\n"
            f"  • Tracked by JARVIS : {'Yes' + pid_info if tracked else 'No'}\n"
            f"  • Port {VITE_PORT} in use   : {'Yes ✅' if port_live else 'No ❌'}\n"
            f"  • URL               : http://localhost:{VITE_PORT}"
        )
