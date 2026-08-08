import psutil
import subprocess
import os

def check_system_health() -> str:
    """Returns the current CPU and RAM usage."""
    try:
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        return f"CPU Usage: {cpu}%\nRAM Usage: {ram.percent}% (Used: {ram.used // (1024**3)}GB / Total: {ram.total // (1024**3)}GB)"
    except Exception as e:
        return f"Error checking system health: {e}"

CHECK_SYSTEM_HEALTH_TOOL = {
    "type": "function",
    "function": {
        "name": "check_system_health",
        "description": "Checks the system's current CPU and RAM usage. Use this when asked about system health, RAM, or CPU.",
        "parameters": {"type": "object", "properties": {}}
    }
}

def launch_app(app_name: str) -> str:
    """Launches a local application like notepad or calc."""
    try:
        print(f"[ACTION] Launching app: {app_name}")
        # Map common names to executables
        app_map = {
            "calculator": "calc.exe",
            "calc": "calc.exe",
            "notepad": "notepad.exe",
            "cmd": "cmd.exe",
            "browser": "msedge.exe" # default Windows browser
        }
        exe = app_map.get(app_name.lower(), app_name)
        
        # We use Popen so it doesn't block
        subprocess.Popen(exe, shell=True)
        return f"Successfully launched {app_name}."
    except Exception as e:
        return f"Error launching app {app_name}: {e}"

LAUNCH_APP_TOOL = {
    "type": "function",
    "function": {
        "name": "launch_app",
        "description": "Launches a local Windows application. Use this when asked to 'open calculator', 'launch notepad', etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "The name of the app to launch (e.g. 'calculator', 'notepad')."
                }
            },
            "required": ["app_name"]
        }
    }
}

def delete_file(file_path: str) -> str:
    """Deletes a file from the disk."""
    try:
        print(f"[ACTION] Deleting file: {file_path}")
        if not os.path.exists(file_path):
            return f"Error: File {file_path} does not exist."
        if not os.path.isfile(file_path):
            return f"Error: {file_path} is not a file."
        
        os.remove(file_path)
        return f"Successfully deleted file: {file_path}"
    except Exception as e:
        return f"Error deleting file {file_path}: {e}"

DELETE_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "delete_file",
        "description": "Deletes a file from the local file system. Use this when the user explicitly asks to delete or remove a file.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The absolute or relative path of the file to delete."
                }
            },
            "required": ["file_path"]
        }
    }
}
