import psutil
import subprocess
import os
from core.verification import ToolResult, VerificationStatus

def check_system_health() -> ToolResult:
    """Returns the current CPU and RAM usage."""
    try:
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        msg = f"CPU Usage: {cpu}%\nRAM Usage: {ram.percent}% (Used: {ram.used // (1024**3)}GB / Total: {ram.total // (1024**3)}GB)"
        return ToolResult(
            status=VerificationStatus.VERIFIED_SUCCESS,
            message=msg,
            evidence="psutil returned valid system metrics."
        )
    except Exception as e:
        return ToolResult(
            status=VerificationStatus.VERIFIED_FAILURE,
            message=f"Error checking system health: {e}",
            evidence="psutil exception raised."
        )

CHECK_SYSTEM_HEALTH_TOOL = {
    "type": "function",
    "function": {
        "name": "check_system_health",
        "description": "Checks the system's current CPU and RAM usage. Use this when asked about system health, RAM, or CPU.",
        "parameters": {"type": "object", "properties": {}}
    }
}

def launch_app(app_name: str) -> ToolResult:
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
        proc = subprocess.Popen(exe, shell=True)
        
        # Verify it started without immediate error
        import time
        time.sleep(0.5)
        if proc.poll() is not None and proc.returncode != 0:
            return ToolResult(
                status=VerificationStatus.VERIFIED_FAILURE,
                message=f"Failed to launch {app_name}.",
                evidence=f"Process exited immediately with code {proc.returncode}."
            )
            
        return ToolResult(
            status=VerificationStatus.VERIFIED_SUCCESS,
            message=f"Successfully launched {app_name}.",
            evidence=f"Process started (PID {proc.pid}) and did not exit immediately."
        )
    except Exception as e:
        return ToolResult(
            status=VerificationStatus.VERIFIED_FAILURE,
            message=f"Error launching app {app_name}: {e}",
            evidence="Exception raised during subprocess.Popen."
        )

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

def delete_file(file_path: str) -> ToolResult:
    """Deletes a file from the disk."""
    try:
        print(f"[ACTION] Deleting file: {file_path}")
        if not os.path.exists(file_path):
            return ToolResult(
                status=VerificationStatus.VERIFIED_FAILURE,
                message=f"Error: File {file_path} does not exist.",
                evidence=f"os.path.exists({file_path}) returned False before deletion."
            )
        if not os.path.isfile(file_path):
            return ToolResult(
                status=VerificationStatus.VERIFIED_FAILURE,
                message=f"Error: {file_path} is not a file.",
                evidence=f"os.path.isfile({file_path}) returned False."
            )
        
        os.remove(file_path)
        
        # VERIFICATION STEP
        if os.path.exists(file_path):
            return ToolResult(
                status=VerificationStatus.VERIFIED_FAILURE,
                message=f"Failed to delete file: {file_path}",
                evidence=f"File still exists after os.remove() attempt. Likely OS lock or permission issue."
            )
            
        return ToolResult(
            status=VerificationStatus.VERIFIED_SUCCESS,
            message=f"Successfully deleted file: {file_path}",
            evidence=f"os.path.exists({file_path}) returned False after deletion."
        )
    except Exception as e:
        return ToolResult(
            status=VerificationStatus.VERIFIED_FAILURE,
            message=f"Error deleting file {file_path}: {e}",
            evidence="Exception raised during deletion attempt."
        )

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
}

def create_procedure(name: str, description: str, trigger: str, steps: list) -> ToolResult:
    """Creates a new procedural memory."""
    try:
        from core.memory_models import ProceduralMemory, ProcedureStep
        from core.memory_manager import MemoryManager
        
        proc_steps = []
        for step in steps:
            proc_steps.append(ProcedureStep(
                agent=step.get("agent", "DevAgent"),
                action=step.get("action", ""),
                description=step.get("description", "")
            ))
            
        mem = ProceduralMemory(
            name=name,
            description=description,
            trigger=trigger,
            steps=proc_steps
        )
        
        # Instantiate temporarily to save
        manager = MemoryManager()
        manager.save_procedural_memory(mem)
        
        return ToolResult(
            status=VerificationStatus.VERIFIED_SUCCESS,
            message=f"Successfully created procedure '{name}'.",
            evidence="MemoryManager saved procedural memory to SQLite and ChromaDB."
        )
    except Exception as e:
        return ToolResult(
            status=VerificationStatus.VERIFIED_FAILURE,
            message=f"Error creating procedure: {e}",
            evidence="Exception raised during creation."
        )

CREATE_PROCEDURE_TOOL = {
    "type": "function",
    "function": {
        "name": "create_procedure",
        "description": "Creates a reusable multi-step procedural memory (automation script/macro). Use this when you have figured out how to solve a repeatable task and want to memorize the workflow.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Short name of the procedure without spaces."
                },
                "description": {
                    "type": "string",
                    "description": "What this procedure does."
                },
                "trigger": {
                    "type": "string",
                    "description": "The natural language phrase that should trigger this procedure (e.g. 'Deploy the backend to staging')."
                },
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "agent": {"type": "string", "description": "Name of the agent to handle this step (e.g. DevAgent, SystemAgent)"},
                            "action": {"type": "string", "description": "The tool or capability to invoke"},
                            "description": {"type": "string", "description": "Natural language instructions for the agent"}
                        },
                        "required": ["agent", "action", "description"]
                    },
                    "description": "List of sequential steps to execute."
                }
            },
            "required": ["name", "description", "trigger", "steps"]
        }
    }
}

def refresh_environment_index(project_root: str) -> ToolResult:
    try:
        from core.environment_index import EnvironmentIndex
        from core.verification import VerificationStatus
        index = EnvironmentIndex()
        knowledge = index.refresh(project_root)
        
        return ToolResult(
            status=VerificationStatus.VERIFIED_SUCCESS,
            message=f"Environment index refreshed for {project_root}",
            evidence=f"Scanned environment {knowledge.environment_id}. Languages: {len(knowledge.languages)}, Frameworks: {len(knowledge.frameworks)}"
        )
    except Exception as e:
        from core.verification import VerificationStatus
        return ToolResult(
            status=VerificationStatus.VERIFIED_FAILURE,
            message=f"Failed to refresh environment index: {e}",
            evidence="Exception raised during indexing."
        )

def query_environment_index(project_root: str, category: str = None) -> ToolResult:
    try:
        from core.environment_index import EnvironmentIndex
        from core.verification import VerificationStatus
        index = EnvironmentIndex()
        facts = index.query(project_root, category)
        
        summary = "\n".join([f"- {f.fact}: {f.value} (Source: {f.source})" for f in facts])
        
        return ToolResult(
            status=VerificationStatus.VERIFIED_SUCCESS,
            message=f"Found {len(facts)} facts for category '{category or 'all'}'.",
            evidence=summary or "No facts found."
        )
    except Exception as e:
        from core.verification import VerificationStatus
        return ToolResult(
            status=VerificationStatus.VERIFIED_FAILURE,
            message=f"Failed to query environment index: {e}",
            evidence="Exception raised during query."
        )

REFRESH_ENV_TOOL = {
    "type": "function",
    "function": {
        "name": "refresh_environment_index",
        "description": "Scans the project root to refresh the local Environment Knowledge Index. Use this when the user asks to scan or update project knowledge.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_root": {
                    "type": "string",
                    "description": "Absolute path to the project root directory to scan."
                }
            },
            "required": ["project_root"]
        }
    }
}

QUERY_ENV_TOOL = {
    "type": "function",
    "function": {
        "name": "query_environment_index",
        "description": "Queries the Environment Knowledge Index for facts about the project (e.g. languages, frameworks, dependencies).",
        "parameters": {
            "type": "object",
            "properties": {
                "project_root": {
                    "type": "string",
                    "description": "Absolute path to the project root."
                },
                "category": {
                    "type": "string",
                    "description": "Optional category to query (e.g., 'languages', 'frameworks', 'dependencies', 'entry_points', 'services'). If omitted, returns all."
                }
            },
            "required": ["project_root"]
        }
    }
}
