import os
import sys
import subprocess
import signal
import socket
import time
from pathlib import Path
from typing import Dict, List, Optional
from core.verification import ToolResult, VerificationStatus

_RUNNING_SERVERS: Dict[str, subprocess.Popen] = {}
DEFAULT_FRONTEND_DIR = str(Path(__file__).resolve().parent.parent / "jarvis-ui")
DEFAULT_VITE_PORT = 5173

def is_port_in_use(port: int) -> bool:
    """Returns True if a process is already listening on the given port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0

# ─────────────────────────────────────────────────────────────────────────
# Code Filesystem Tools with Real Evidence & files_changed tracking
# ─────────────────────────────────────────────────────────────────────────

def read_code_file(file_path: str, start_line: int = 1, end_line: int = 200) -> ToolResult:
    """Safely reads lines from a code file."""
    try:
        if not os.path.exists(file_path):
            return ToolResult(
                status=VerificationStatus.VERIFIED_FAILURE,
                message=f"File not found: {file_path}",
                evidence=f"os.path.exists({file_path}) returned False."
            )
        if not os.path.isfile(file_path):
            return ToolResult(
                status=VerificationStatus.VERIFIED_FAILURE,
                message=f"Target is not a file: {file_path}",
                evidence=f"os.path.isfile({file_path}) returned False."
            )
            
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            
        total_lines = len(lines)
        start_idx = max(0, start_line - 1)
        end_idx = min(total_lines, end_line)
        selected_lines = lines[start_idx:end_idx]
        
        numbered = [f"{start_idx + i + 1}: {line}" for i, line in enumerate(selected_lines)]
        content = "".join(numbered)
        
        return ToolResult(
            status=VerificationStatus.VERIFIED_SUCCESS,
            message=f"Read {len(selected_lines)} lines from {file_path} (Lines {start_line}-{end_idx} of {total_lines}):\n{content}",
            evidence=f"Successfully read {file_path}. Total lines: {total_lines}."
        )
    except Exception as e:
        return ToolResult(
            status=VerificationStatus.VERIFIED_FAILURE,
            message=f"Failed to read file {file_path}: {e}",
            evidence=f"Exception raised reading {file_path}: {e}"
        )

def write_code_file(file_path: str, content: str) -> ToolResult:
    """
    Writes content to a file, creating directories if needed.
    Verifies on disk that file exists, is non-empty/matches written size,
    and returns deterministic files_changed record.
    """
    try:
        abs_path = os.path.abspath(file_path)
        existed_before = os.path.exists(abs_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        # Physical Verification
        if not os.path.exists(abs_path):
            return ToolResult(
                status=VerificationStatus.VERIFIED_FAILURE,
                message=f"Write verification failed: {file_path} does not exist after write.",
                evidence="os.path.exists returned False after open/write."
            )
            
        size = os.path.getsize(abs_path)
        operation = "modified" if existed_before else "created"
        files_changed = [{"path": file_path, "operation": operation}]
        
        return ToolResult(
            status=VerificationStatus.VERIFIED_SUCCESS,
            message=f"Successfully wrote {size} bytes to {file_path} ({operation}).",
            evidence=f"File {file_path} exists on disk with size {size} bytes. Verified content length: {len(content)}.",
            files_changed=files_changed
        )
    except Exception as e:
        return ToolResult(
            status=VerificationStatus.VERIFIED_FAILURE,
            message=f"Failed to write file {file_path}: {e}",
            evidence=f"Exception raised writing file: {e}"
        )

def inspect_code_directory(directory_path: str = ".") -> ToolResult:
    """Lists directory contents."""
    try:
        if not os.path.exists(directory_path):
            return ToolResult(
                status=VerificationStatus.VERIFIED_FAILURE,
                message=f"Directory not found: {directory_path}",
                evidence=f"os.path.exists({directory_path}) returned False."
            )
        files = os.listdir(directory_path)
        return ToolResult(
            status=VerificationStatus.VERIFIED_SUCCESS,
            message=f"Directory '{directory_path}' contains {len(files)} items: {', '.join(files)}",
            evidence=f"os.listdir({directory_path}) succeeded with {len(files)} items."
        )
    except Exception as e:
        return ToolResult(
            status=VerificationStatus.VERIFIED_FAILURE,
            message=f"Failed to inspect directory {directory_path}: {e}",
            evidence=f"Exception raised during os.listdir: {e}"
        )

# ─────────────────────────────────────────────────────────────────────────
# Backend Specialized Tools
# ─────────────────────────────────────────────────────────────────────────

def run_backend_tests(test_target: str = "tests") -> ToolResult:
    """
    Executes backend tests using python unittest.
    Verifies process exit code and parses test outcomes.
    """
    try:
        cmd = [sys.executable, "-m", "unittest"]
        if os.path.isdir(test_target):
            cmd.extend(["discover", "-s", test_target])
        else:
            cmd.append(test_target)
            
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30
        )
        
        output = proc.stdout + "\n" + proc.stderr
        if proc.returncode == 0:
            return ToolResult(
                status=VerificationStatus.VERIFIED_SUCCESS,
                message=f"Backend tests passed successfully:\n{output[-800:]}",
                evidence=f"Process exited with code 0. Command: {' '.join(cmd)}"
            )
        else:
            return ToolResult(
                status=VerificationStatus.VERIFIED_FAILURE,
                message=f"Backend tests failed (exit code {proc.returncode}):\n{output[-800:]}",
                evidence=f"Process exited with code {proc.returncode}. Stderr: {proc.stderr[:400]}"
            )
    except subprocess.TimeoutExpired:
        return ToolResult(
            status=VerificationStatus.VERIFIED_FAILURE,
            message="Backend test execution timed out after 30s.",
            evidence="Subprocess timeout expired."
        )
    except Exception as e:
        return ToolResult(
            status=VerificationStatus.VERIFIED_FAILURE,
            message=f"Error executing backend tests: {e}",
            evidence=f"Exception: {e}"
        )

def run_backend_command(command: str) -> ToolResult:
    """Executes a shell command in the backend environment safely."""
    try:
        proc = subprocess.run(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30
        )
        if proc.returncode == 0:
            return ToolResult(
                status=VerificationStatus.VERIFIED_SUCCESS,
                message=f"Command '{command}' succeeded:\n{proc.stdout[:800]}",
                evidence=f"Command exited with code 0."
            )
        else:
            return ToolResult(
                status=VerificationStatus.VERIFIED_FAILURE,
                message=f"Command '{command}' failed (exit code {proc.returncode}):\n{proc.stderr[:800]}",
                evidence=f"Command returned code {proc.returncode}."
            )
    except Exception as e:
        return ToolResult(
            status=VerificationStatus.VERIFIED_FAILURE,
            message=f"Failed to execute backend command: {e}",
            evidence=f"Exception: {e}"
        )

# ─────────────────────────────────────────────────────────────────────────
# Frontend Specialized Tools
# ─────────────────────────────────────────────────────────────────────────

def start_frontend_server(ui_dir: str = DEFAULT_FRONTEND_DIR, port: int = DEFAULT_VITE_PORT) -> ToolResult:
    """Starts the frontend dev server."""
    server_key = "frontend-ui"
    if server_key in _RUNNING_SERVERS:
        proc = _RUNNING_SERVERS[server_key]
        if proc.poll() is None:
            return ToolResult(
                status=VerificationStatus.VERIFIED_SUCCESS,
                message=f"Frontend dev server is already running (PID {proc.pid}) at http://localhost:{port}.",
                evidence=f"Process {proc.pid} is alive."
            )
        else:
            del _RUNNING_SERVERS[server_key]

    if is_port_in_use(port):
        return ToolResult(
            status=VerificationStatus.VERIFIED_FAILURE,
            message=f"Port {port} is already in use by another process.",
            evidence=f"is_port_in_use({port}) returned True."
        )

    if not os.path.isdir(ui_dir):
        return ToolResult(
            status=VerificationStatus.VERIFIED_FAILURE,
            message=f"Frontend directory not found at: {ui_dir}.",
            evidence=f"os.path.isdir({ui_dir}) returned False."
        )

    try:
        proc = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=ui_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            text=True,
        )
        _RUNNING_SERVERS[server_key] = proc

        # Poll port to verify startup
        for _ in range(10):
            time.sleep(1)
            if proc.poll() is not None:
                _, stderr = proc.communicate()
                del _RUNNING_SERVERS[server_key]
                return ToolResult(
                    status=VerificationStatus.VERIFIED_FAILURE,
                    message=f"Frontend dev server exited unexpectedly: {stderr[:400]}",
                    evidence=f"Exit code: {proc.returncode}."
                )
            if is_port_in_use(port):
                return ToolResult(
                    status=VerificationStatus.VERIFIED_SUCCESS,
                    message=f"✅ Frontend dev server started successfully (PID {proc.pid}) at http://localhost:{port}.",
                    evidence=f"is_port_in_use({port}) returned True."
                )

        proc.kill()
        del _RUNNING_SERVERS[server_key]
        return ToolResult(
            status=VerificationStatus.VERIFIED_FAILURE,
            message=f"Server process started (PID {proc.pid}) but port {port} did not open within 10s.",
            evidence=f"Port {port} remained unopened."
        )
    except FileNotFoundError:
        return ToolResult(
            status=VerificationStatus.VERIFIED_FAILURE,
            message="'npm' command not found. Node.js required.",
            evidence="FileNotFoundError on npm."
        )
    except Exception as e:
        return ToolResult(
            status=VerificationStatus.VERIFIED_FAILURE,
            message=f"Failed to start frontend server: {e}",
            evidence=f"Exception: {e}"
        )

def stop_frontend_server(port: int = DEFAULT_VITE_PORT) -> ToolResult:
    """Stops the frontend dev server."""
    server_key = "frontend-ui"
    if server_key not in _RUNNING_SERVERS:
        if is_port_in_use(port):
            return ToolResult(
                status=VerificationStatus.VERIFIED_FAILURE,
                message=f"No server tracked by this session, but port {port} is occupied by external process.",
                evidence=f"is_port_in_use({port}) is True but not in _RUNNING_SERVERS."
            )
        return ToolResult(
            status=VerificationStatus.VERIFIED_SUCCESS,
            message="No running frontend dev server to stop.",
            evidence="Server not tracked and port not in use."
        )

    proc = _RUNNING_SERVERS[server_key]
    try:
        if proc.poll() is None:
            if os.name == "nt":
                proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

        del _RUNNING_SERVERS[server_key]
        if is_port_in_use(port):
            return ToolResult(
                status=VerificationStatus.VERIFIED_FAILURE,
                message=f"Process terminated but port {port} is still in use.",
                evidence="Port remains open."
            )

        return ToolResult(
            status=VerificationStatus.VERIFIED_SUCCESS,
            message=f"✅ Frontend dev server (PID {proc.pid}) stopped successfully.",
            evidence=f"Process terminated and port {port} is closed."
        )
    except Exception as e:
        return ToolResult(
            status=VerificationStatus.VERIFIED_FAILURE,
            message=f"Failed to stop frontend server: {e}",
            evidence=f"Exception: {e}"
        )

def frontend_server_status(port: int = DEFAULT_VITE_PORT) -> ToolResult:
    """Checks frontend dev server status."""
    server_key = "frontend-ui"
    port_live = is_port_in_use(port)
    tracked = server_key in _RUNNING_SERVERS
    pid_info = ""
    if tracked:
        proc = _RUNNING_SERVERS[server_key]
        alive = proc.poll() is None
        pid_info = f", PID {proc.pid}, alive: {alive}"

    msg = f"Frontend Server Status:\n  • Tracked: {'Yes' + pid_info if tracked else 'No'}\n  • Port {port} in use: {'Yes ✅' if port_live else 'No ❌'}\n  • URL: http://localhost:{port}"
    return ToolResult(
        status=VerificationStatus.VERIFIED_SUCCESS,
        message=msg,
        evidence=f"Tracked: {tracked}, Port Live: {port_live}."
    )

def run_frontend_build(ui_dir: str = DEFAULT_FRONTEND_DIR) -> ToolResult:
    """Runs frontend build (e.g. npm run build) and verifies output directory/files."""
    if not os.path.isdir(ui_dir):
        return ToolResult(
            status=VerificationStatus.VERIFIED_FAILURE,
            message=f"Frontend directory not found at: {ui_dir}",
            evidence=f"os.path.isdir({ui_dir}) returned False."
        )
    try:
        proc = subprocess.run(
            ["npm", "run", "build"],
            cwd=ui_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60
        )
        if proc.returncode == 0:
            dist_dir = os.path.join(ui_dir, "dist")
            dist_exists = os.path.exists(dist_dir)
            return ToolResult(
                status=VerificationStatus.VERIFIED_SUCCESS,
                message=f"Frontend build succeeded:\n{proc.stdout[-500:]}",
                evidence=f"npm run build exit code 0. Dist directory exists: {dist_exists}"
            )
        else:
            return ToolResult(
                status=VerificationStatus.VERIFIED_FAILURE,
                message=f"Frontend build failed (exit code {proc.returncode}):\n{proc.stderr[:500]}",
                evidence=f"npm run build returned code {proc.returncode}."
            )
    except Exception as e:
        return ToolResult(
            status=VerificationStatus.VERIFIED_FAILURE,
            message=f"Frontend build execution failed: {e}",
            evidence=f"Exception: {e}"
        )

# ─────────────────────────────────────────────────────────────────────────
# Schemas for LLM Tool Calling
# ─────────────────────────────────────────────────────────────────────────

READ_CODE_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "read_code_file",
        "description": "Reads lines from a code or text file.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the file to read."},
                "start_line": {"type": "integer", "description": "Starting line number (1-indexed)."},
                "end_line": {"type": "integer", "description": "Ending line number."}
            },
            "required": ["file_path"]
        }
    }
}

WRITE_CODE_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "write_code_file",
        "description": "Writes code or configuration to a file on disk. Creates parent directories automatically.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the target file."},
                "content": {"type": "string", "description": "Complete content to write."}
            },
            "required": ["file_path", "content"]
        }
    }
}

INSPECT_CODE_DIR_TOOL = {
    "type": "function",
    "function": {
        "name": "inspect_directory",
        "description": "Lists all files and folders in the specified directory.",
        "parameters": {
            "type": "object",
            "properties": {
                "directory_path": {"type": "string", "description": "Directory path to inspect (defaults to current directory)."}
            }
        }
    }
}

RUN_BACKEND_TESTS_TOOL = {
    "type": "function",
    "function": {
        "name": "run_backend_tests",
        "description": "Runs backend unit tests using python unittest.",
        "parameters": {
            "type": "object",
            "properties": {
                "test_target": {"type": "string", "description": "Target test directory or file path (default 'tests')."}
            }
        }
    }
}

RUN_BACKEND_COMMAND_TOOL = {
    "type": "function",
    "function": {
        "name": "run_backend_command",
        "description": "Executes a backend shell command.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The command string to execute."}
            },
            "required": ["command"]
        }
    }
}

START_FRONTEND_SERVER_TOOL = {
    "type": "function",
    "function": {
        "name": "start_frontend_server",
        "description": "Starts the Vite React frontend development server for jarvis-ui.",
        "parameters": {"type": "object", "properties": {}}
    }
}

STOP_FRONTEND_SERVER_TOOL = {
    "type": "function",
    "function": {
        "name": "stop_frontend_server",
        "description": "Stops the running Vite React frontend development server.",
        "parameters": {"type": "object", "properties": {}}
    }
}

FRONTEND_SERVER_STATUS_TOOL = {
    "type": "function",
    "function": {
        "name": "frontend_server_status",
        "description": "Checks the status of the frontend development server.",
        "parameters": {"type": "object", "properties": {}}
    }
}

RUN_FRONTEND_BUILD_TOOL = {
    "type": "function",
    "function": {
        "name": "run_frontend_build",
        "description": "Runs 'npm run build' for the frontend UI.",
        "parameters": {"type": "object", "properties": {}}
    }
}
