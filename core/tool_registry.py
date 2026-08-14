import threading
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field, asdict
from core.execution_gate import RiskLevel
from core.observability import observability_manager, ObservabilityEvent

@dataclass
class ToolDefinition:
    name: str
    description: str
    owner: str
    capabilities: List[str] = field(default_factory=list)
    agents: List[str] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.READ_ONLY
    confirmation_required: bool = False
    retryable: bool = True
    idempotent: bool = True
    max_retries: int = 2
    verification_contract: str = "OBSERVABLE_SYSTEM_STATE"
    input_schema: Dict[str, Any] = field(default_factory=lambda: {"type": "object", "properties": {}, "required": []})
    output_schema: Optional[Dict[str, Any]] = None
    side_effects: bool = False
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["risk_level"] = self.risk_level.name if hasattr(self.risk_level, "name") else str(self.risk_level)
        return data

class ToolRegistry:
    """
    Centralized, Authoritative Tool Registry & Capability Discovery layer (Task 11).
    Provides metadata, schema validation, capability mapping, and discoverability.
    
    IMPORTANT: The Tool Registry is METADATA/DISCOVERY ONLY.
    It does NOT execute tools directly and does NOT grant permissions.
    All executions must pass through ExecutionGate.
    """
    def __init__(self):
        self._lock = threading.RLock()
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> bool:
        """
        Registers a tool definition after validating safety and metadata rules.
        Rejects duplicates, missing risk, missing verification contracts,
        or invalid retry configurations.
        """
        with self._lock:
            # 1. Reject invalid name
            if not tool.name or not isinstance(tool.name, str) or not tool.name.strip():
                raise ValueError("Tool name must be a non-empty string.")
            name = tool.name.strip()
            
            # 2. Reject duplicate registration
            if name in self._tools:
                raise ValueError(f"Tool '{name}' is already registered in ToolRegistry.")
                
            # 3. Validate RiskLevel
            if tool.risk_level is None or not isinstance(tool.risk_level, (RiskLevel, int)):
                raise ValueError(f"Tool '{name}' must have a valid RiskLevel.")
                
            # 4. Validate Verification Contract
            if not tool.verification_contract or not isinstance(tool.verification_contract, str) or not tool.verification_contract.strip():
                raise ValueError(f"Tool '{name}' must declare an explicit verification contract.")
            if tool.verification_contract.strip().lower() in ("success string", "none", "true"):
                raise ValueError(f"Tool '{name}' has an invalid verification contract ('{tool.verification_contract}'). Must specify observable state.")
                
            # 5. Validate Retry Configuration
            if tool.risk_level == RiskLevel.DESTRUCTIVE:
                if tool.retryable or tool.max_retries > 0:
                    raise ValueError(f"Destructive tool '{name}' cannot be declared retryable or have max_retries > 0.")
            if tool.confirmation_required and tool.retryable:
                raise ValueError(f"Confirmation-gated tool '{name}' cannot be declared automatically retryable.")
                
            # 6. Validate input_schema
            if not isinstance(tool.input_schema, dict):
                raise ValueError(f"Tool '{name}' input_schema must be a dictionary.")

            self._tools[name] = tool
            
            observability_manager.emit_event(ObservabilityEvent(
                event_type="TOOL_REGISTERED",
                tool=name,
                metadata={
                    "owner": tool.owner,
                    "risk_level": tool.risk_level.name if hasattr(tool.risk_level, "name") else str(tool.risk_level),
                    "retryable": tool.retryable
                }
            ))
            return True

    def unregister(self, tool_name: str) -> bool:
        """Unregisters a tool by name."""
        with self._lock:
            if tool_name in self._tools:
                del self._tools[tool_name]
                observability_manager.emit_event(ObservabilityEvent(
                    event_type="TOOL_UNREGISTERED",
                    tool=tool_name
                ))
                return True
            return False

    def get(self, tool_name: str) -> Optional[ToolDefinition]:
        """Retrieves a tool definition by name."""
        with self._lock:
            return self._tools.get(tool_name)

    def list(self, enabled_only: bool = True) -> List[ToolDefinition]:
        """Lists registered tools."""
        with self._lock:
            if enabled_only:
                return [t for t in self._tools.values() if t.enabled]
            return list(self._tools.values())

    def search(self, query: str) -> List[ToolDefinition]:
        """Searches tools by name, description, capability, or owner."""
        q = query.lower().strip()
        with self._lock:
            results = []
            for t in self._tools.values():
                if (q in t.name.lower() or 
                    q in t.description.lower() or 
                    q in t.owner.lower() or 
                    any(q in c.lower() for c in t.capabilities) or
                    any(q in a.lower() for a in t.agents)):
                    results.append(t)
            return results

    def get_for_agent(self, agent_name: str) -> List[ToolDefinition]:
        """Discovers tools available for a specific agent."""
        with self._lock:
            return [t for t in self._tools.values() if t.enabled and (agent_name in t.agents or "all" in t.agents or "shared" in t.agents)]

    def get_for_capability(self, capability: str) -> List[ToolDefinition]:
        """Discovers tools providing a specific capability."""
        with self._lock:
            return [t for t in self._tools.values() if t.enabled and capability in t.capabilities]

    def get_by_risk(self, risk_level: RiskLevel) -> List[ToolDefinition]:
        """Returns all tools with a specific RiskLevel."""
        with self._lock:
            return [t for t in self._tools.values() if t.risk_level == risk_level]

    def get_retryable_tools(self) -> List[ToolDefinition]:
        """Returns all tools that are safe to retry."""
        with self._lock:
            return [t for t in self._tools.values() if t.enabled and t.retryable]

    def validate_arguments(self, tool_name: str, kwargs: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validates input arguments against the tool's registered input_schema before execution.
        Checks required fields, type matches, and unexpected parameters.
        """
        tool = self.get(tool_name)
        if not tool:
            return False, f"Tool '{tool_name}' is not registered in ToolRegistry."
            
        schema = tool.input_schema or {}
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        # 1. Check required parameters
        for req in required:
            if req not in kwargs:
                return False, f"Missing required parameter '{req}' for tool '{tool_name}'."
                
        # 2. Check types and unexpected parameters
        for key, val in kwargs.items():
            if key not in properties:
                # If properties are defined and key not in properties, reject unexpected param
                if properties:
                    return False, f"Unexpected parameter '{key}' for tool '{tool_name}'."
            else:
                expected_type = properties[key].get("type")
                if expected_type and val is not None:
                    if expected_type == "string" and not isinstance(val, str):
                        return False, f"Parameter '{key}' must be of type string, got {type(val).__name__}."
                    elif expected_type == "integer" and (not isinstance(val, int) or isinstance(val, bool)):
                        return False, f"Parameter '{key}' must be of type integer, got {type(val).__name__}."
                    elif expected_type == "boolean" and not isinstance(val, bool):
                        return False, f"Parameter '{key}' must be of type boolean, got {type(val).__name__}."
                    elif expected_type == "array" and not isinstance(val, list):
                        return False, f"Parameter '{key}' must be of type array/list, got {type(val).__name__}."
                    elif expected_type == "object" and not isinstance(val, dict):
                        return False, f"Parameter '{key}' must be of type object/dict, got {type(val).__name__}."

        return True, None

def init_standard_tool_registry() -> ToolRegistry:
    """Initializes the authoritative tool inventory for JARVIS (Tasks 1-11)."""
    reg = ToolRegistry()
    
    # ── System & General Tools ──────────────────────────────────────────────
    reg.register(ToolDefinition(
        name="search_internet",
        description="Searches the internet for real-time information, news, weather, or facts using DuckDuckGo.",
        owner="System",
        capabilities=["internet_search", "shared_dev"],
        agents=["System", "MasterAgent", "BackendAgent", "FrontendAgent", "DevAgent"],
        risk_level=RiskLevel.READ_ONLY,
        confirmation_required=False,
        retryable=True,
        idempotent=True,
        max_retries=2,
        verification_contract="DDGS_QUERY_RESULTS",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "description": "Max results to return"}
            },
            "required": ["query"]
        },
        side_effects=False
    ))
    
    reg.register(ToolDefinition(
        name="open_url",
        description="Opens a website URL in the user's default web browser.",
        owner="System",
        capabilities=["system_control"],
        agents=["System", "MasterAgent", "FrontendAgent", "DevAgent"],
        risk_level=RiskLevel.REVERSIBLE,
        confirmation_required=False,
        retryable=True,
        idempotent=True,
        max_retries=2,
        verification_contract="BROWSER_INVOCATION_RETURNED",
        input_schema={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Full URL to open"}
            },
            "required": ["url"]
        },
        side_effects=True
    ))

    reg.register(ToolDefinition(
        name="check_system_health",
        description="Checks current system CPU and RAM usage via psutil.",
        owner="System",
        capabilities=["system_diagnostics"],
        agents=["System", "MasterAgent", "DevAgent"],
        risk_level=RiskLevel.READ_ONLY,
        confirmation_required=False,
        retryable=True,
        idempotent=True,
        max_retries=2,
        verification_contract="PSUTIL_METRICS_FETCHED",
        input_schema={"type": "object", "properties": {}, "required": []},
        side_effects=False
    ))

    reg.register(ToolDefinition(
        name="launch_app",
        description="Launches a local desktop application like calculator or notepad.",
        owner="System",
        capabilities=["system_control"],
        agents=["System", "MasterAgent"],
        risk_level=RiskLevel.REVERSIBLE,
        confirmation_required=False,
        retryable=True,
        idempotent=False,
        max_retries=2,
        verification_contract="PROCESS_ALIVE_NON_ZERO_EXIT",
        input_schema={
            "type": "object",
            "properties": {
                "app_name": {"type": "string", "description": "Name of app to launch"}
            },
            "required": ["app_name"]
        },
        side_effects=True
    ))

    reg.register(ToolDefinition(
        name="delete_file",
        description="Deletes a file from the local file system. Destructive operation.",
        owner="System",
        capabilities=["fs_delete"],
        agents=["System", "BackendAgent", "DevAgent"],
        risk_level=RiskLevel.DESTRUCTIVE,
        confirmation_required=True,
        retryable=False,
        idempotent=False,
        max_retries=0,
        verification_contract="FILE_ABSENT_ON_DISK",
        input_schema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Absolute or relative file path"}
            },
            "required": ["file_path"]
        },
        side_effects=True
    ))

    # ── Memory Tools ────────────────────────────────────────────────────────
    reg.register(ToolDefinition(
        name="create_procedure",
        description="Creates a reusable multi-step procedural memory (macro/workflow).",
        owner="Memory",
        capabilities=["memory_management"],
        agents=["System", "MasterAgent", "DevAgent"],
        risk_level=RiskLevel.REVERSIBLE,
        confirmation_required=False,
        retryable=True,
        idempotent=True,
        max_retries=2,
        verification_contract="PROCEDURAL_MEMORY_SAVED",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Short name"},
                "description": {"type": "string", "description": "Description"},
                "trigger": {"type": "string", "description": "Trigger phrase"},
                "steps": {"type": "array", "description": "List of procedure steps"}
            },
            "required": ["name", "description", "trigger", "steps"]
        },
        side_effects=True
    ))

    reg.register(ToolDefinition(
        name="remember_file",
        description="Ingests a file into long-term ChromaDB vector memory.",
        owner="Memory",
        capabilities=["memory_management"],
        agents=["System", "MasterAgent"],
        risk_level=RiskLevel.REVERSIBLE,
        confirmation_required=False,
        retryable=True,
        idempotent=True,
        max_retries=2,
        verification_contract="CHROMA_INGESTION_COMPLETED",
        input_schema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to file"}
            },
            "required": ["file_path"]
        },
        side_effects=True
    ))

    reg.register(ToolDefinition(
        name="switch_voice_profile",
        description="Switches the TTS voice profile for the active session.",
        owner="System",
        capabilities=["voice_control"],
        agents=["System", "MasterAgent"],
        risk_level=RiskLevel.REVERSIBLE,
        confirmation_required=False,
        retryable=True,
        idempotent=True,
        max_retries=2,
        verification_contract="VOICE_PROFILE_SET",
        input_schema={
            "type": "object",
            "properties": {
                "profile_name": {"type": "string", "description": "Voice profile name"}
            },
            "required": ["profile_name"]
        },
        side_effects=True
    ))

    # ── Environment Tools ───────────────────────────────────────────────────
    reg.register(ToolDefinition(
        name="refresh_environment_index",
        description="Scans project root to refresh the local Environment Knowledge Index.",
        owner="Environment",
        capabilities=["environment_indexing"],
        agents=["System", "MasterAgent", "BackendAgent", "FrontendAgent", "DevAgent"],
        risk_level=RiskLevel.READ_ONLY,
        confirmation_required=False,
        retryable=True,
        idempotent=True,
        max_retries=2,
        verification_contract="ENVIRONMENT_SCANNED",
        input_schema={
            "type": "object",
            "properties": {
                "project_root": {"type": "string", "description": "Path to project root"}
            },
            "required": ["project_root"]
        },
        side_effects=False
    ))

    reg.register(ToolDefinition(
        name="query_environment_index",
        description="Queries facts from the Environment Knowledge Index.",
        owner="Environment",
        capabilities=["environment_query"],
        agents=["System", "MasterAgent", "BackendAgent", "FrontendAgent", "DevAgent"],
        risk_level=RiskLevel.READ_ONLY,
        confirmation_required=False,
        retryable=True,
        idempotent=True,
        max_retries=2,
        verification_contract="ENVIRONMENT_FACTS_RETURNED",
        input_schema={
            "type": "object",
            "properties": {
                "project_root": {"type": "string", "description": "Path to project root"},
                "category": {"type": "string", "description": "Optional fact category"}
            },
            "required": ["project_root"]
        },
        side_effects=False
    ))

    # ── Development & Filesystem Tools ──────────────────────────────────────
    reg.register(ToolDefinition(
        name="read_code_file",
        description="Reads line range from a code file on disk.",
        owner="DevTools",
        capabilities=["code_reading", "fs_read", "backend_code", "frontend_code"],
        agents=["BackendAgent", "FrontendAgent", "DevAgent", "System"],
        risk_level=RiskLevel.READ_ONLY,
        confirmation_required=False,
        retryable=True,
        idempotent=True,
        max_retries=2,
        verification_contract="FILE_LINES_READ_ON_DISK",
        input_schema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to code file"},
                "start_line": {"type": "integer", "description": "Start line (1-based)"},
                "end_line": {"type": "integer", "description": "End line (inclusive)"}
            },
            "required": ["file_path"]
        },
        side_effects=False
    ))

    reg.register(ToolDefinition(
        name="write_code_file",
        description="Writes content to a code file, verifies on disk, and records files_changed.",
        owner="DevTools",
        capabilities=["backend_code", "frontend_code", "fs_write"],
        agents=["BackendAgent", "FrontendAgent", "DevAgent"],
        risk_level=RiskLevel.REVERSIBLE,
        confirmation_required=False,
        retryable=True,
        idempotent=True,
        max_retries=2,
        verification_contract="FILE_EXISTS_SIZE_MATCH_ON_DISK",
        input_schema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "File path to write to"},
                "content": {"type": "string", "description": "File content"}
            },
            "required": ["file_path", "content"]
        },
        side_effects=True
    ))

    reg.register(ToolDefinition(
        name="inspect_directory",
        description="Lists files and directories in a given path.",
        owner="DevTools",
        capabilities=["code_reading", "fs_read"],
        agents=["BackendAgent", "FrontendAgent", "DevAgent"],
        risk_level=RiskLevel.READ_ONLY,
        confirmation_required=False,
        retryable=True,
        idempotent=True,
        max_retries=2,
        verification_contract="DIRECTORY_LISTED_ON_DISK",
        input_schema={
            "type": "object",
            "properties": {
                "directory_path": {"type": "string", "description": "Directory path to inspect"}
            },
            "required": []
        },
        side_effects=False
    ))

    # ── Backend Specialized Tools ───────────────────────────────────────────
    reg.register(ToolDefinition(
        name="run_backend_tests",
        description="Executes backend unit tests and returns structured outcome.",
        owner="DevTools",
        capabilities=["backend_tests"],
        agents=["BackendAgent", "DevAgent"],
        risk_level=RiskLevel.READ_ONLY,
        confirmation_required=False,
        retryable=True,
        idempotent=True,
        max_retries=2,
        verification_contract="EXIT_CODE_ZERO_TEST_OUTPUT",
        input_schema={
            "type": "object",
            "properties": {
                "test_target": {"type": "string", "description": "Test file or directory"}
            },
            "required": []
        },
        side_effects=False
    ))

    reg.register(ToolDefinition(
        name="run_backend_command",
        description="Executes a shell command in backend environment.",
        owner="DevTools",
        capabilities=["backend_command", "process_execution"],
        agents=["BackendAgent", "DevAgent"],
        risk_level=RiskLevel.REVERSIBLE,
        confirmation_required=False,
        retryable=True,
        idempotent=False,
        max_retries=2,
        verification_contract="EXIT_CODE_ZERO_COMMAND_OUTPUT",
        input_schema={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run"}
            },
            "required": ["command"]
        },
        side_effects=True
    ))

    # ── Frontend Specialized Tools ──────────────────────────────────────────
    reg.register(ToolDefinition(
        name="start_frontend_server",
        description="Starts the Vite frontend dev server and verifies port listener.",
        owner="DevTools",
        capabilities=["frontend_server"],
        agents=["FrontendAgent", "DevAgent"],
        risk_level=RiskLevel.REVERSIBLE,
        confirmation_required=False,
        retryable=True,
        idempotent=False,
        max_retries=2,
        verification_contract="PORT_LISTENING_PROCESS_ALIVE",
        input_schema={
            "type": "object",
            "properties": {
                "ui_dir": {"type": "string", "description": "Frontend UI directory path"},
                "port": {"type": "integer", "description": "Vite dev server port"}
            },
            "required": []
        },
        side_effects=True
    ))

    reg.register(ToolDefinition(
        name="stop_frontend_server",
        description="Stops the active frontend dev server process.",
        owner="DevTools",
        capabilities=["frontend_server"],
        agents=["FrontendAgent", "DevAgent"],
        risk_level=RiskLevel.REVERSIBLE,
        confirmation_required=False,
        retryable=True,
        idempotent=True,
        max_retries=2,
        verification_contract="PORT_CLOSED_PROCESS_STOPPED",
        input_schema={
            "type": "object",
            "properties": {
                "port": {"type": "integer", "description": "Port to stop"}
            },
            "required": []
        },
        side_effects=True
    ))

    reg.register(ToolDefinition(
        name="server_status",
        description="Checks if frontend dev server is running and port is listening.",
        owner="DevTools",
        capabilities=["frontend_server"],
        agents=["FrontendAgent", "DevAgent"],
        risk_level=RiskLevel.READ_ONLY,
        confirmation_required=False,
        retryable=True,
        idempotent=True,
        max_retries=2,
        verification_contract="PORT_AND_PROCESS_INSPECTED",
        input_schema={
            "type": "object",
            "properties": {
                "port": {"type": "integer", "description": "Port to inspect"}
            },
            "required": []
        },
        side_effects=False
    ))

    reg.register(ToolDefinition(
        name="run_frontend_build",
        description="Runs frontend build (e.g. npm run build) and verifies output dist.",
        owner="DevTools",
        capabilities=["frontend_build"],
        agents=["FrontendAgent", "DevAgent"],
        risk_level=RiskLevel.REVERSIBLE,
        confirmation_required=False,
        retryable=True,
        idempotent=True,
        max_retries=2,
        verification_contract="DIST_DIRECTORY_CREATED_EXIT_ZERO",
        input_schema={
            "type": "object",
            "properties": {
                "ui_dir": {"type": "string", "description": "Frontend UI directory path"}
            },
            "required": []
        },
        side_effects=True
    ))

    reg.register(ToolDefinition(
        name="run_frontend_tests",
        description="Runs frontend test suite and verifies exit code.",
        owner="DevTools",
        capabilities=["frontend_tests"],
        agents=["FrontendAgent", "DevAgent"],
        risk_level=RiskLevel.READ_ONLY,
        confirmation_required=False,
        retryable=True,
        idempotent=True,
        max_retries=2,
        verification_contract="EXIT_CODE_ZERO_TEST_OUTPUT",
        input_schema={
            "type": "object",
            "properties": {
                "ui_dir": {"type": "string", "description": "Frontend directory"}
            },
            "required": []
        },
        side_effects=False
    ))

    return reg

# Authoritative global tool registry instance
tool_registry = init_standard_tool_registry()
