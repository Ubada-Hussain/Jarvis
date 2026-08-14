import os
import re
import uuid
from enum import Enum
from typing import Dict, List, Any, Optional, Tuple
from pydantic import BaseModel, Field

from core.environment_index import EnvironmentIndex
from core.environment_models import EnvironmentKnowledge, EnvironmentFact
from core.memory_manager import MemoryManager
from core.tool_registry import ToolRegistry, tool_registry
from core.audit_logger import SQLiteAuditLogger
from core.observability import observability_manager, ObservabilityEvent

class IntentType(str, Enum):
    INFORMATION_REQUEST = "INFORMATION_REQUEST"
    CODE_CHANGE = "CODE_CHANGE"
    FILE_OPERATION = "FILE_OPERATION"
    SYSTEM_OPERATION = "SYSTEM_OPERATION"
    FRONTEND_TASK = "FRONTEND_TASK"
    BACKEND_TASK = "BACKEND_TASK"
    FULL_STACK_TASK = "FULL_STACK_TASK"
    RESEARCH_TASK = "RESEARCH_TASK"
    MEMORY_OPERATION = "MEMORY_OPERATION"
    ENVIRONMENT_QUERY = "ENVIRONMENT_QUERY"
    MIXED_TASK = "MIXED_TASK"
    UNKNOWN = "UNKNOWN"

class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class StructuredIntent(BaseModel):
    request_id: str
    original_request: str
    normalized_request: str
    intent_type: IntentType
    entities: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    requested_actions: List[str] = Field(default_factory=list)
    environment_context: Dict[str, Any] = Field(default_factory=dict)
    relevant_memories: List[Dict[str, Any]] = Field(default_factory=list)
    relevant_procedures: List[Dict[str, Any]] = Field(default_factory=list)
    candidate_agents: List[str] = Field(default_factory=list)
    candidate_tools: List[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    confidence_score: float = 0.5
    ambiguity: bool = False
    ambiguity_reasons: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    procedure_match: Optional[Dict[str, Any]] = None
    requires_clarification: bool = False

class ContextResolver:
    """
    Unified Context & Intent Resolution Layer (Task 12).
    Synthesizes EnvironmentIndex, EpisodicMemory, ProceduralMemory, and ToolRegistry
    into an authoritative StructuredIntent before TaskPlanner creates a TaskGraph.
    
    IMPORTANT: ContextResolver is a read/analysis layer only.
    It NEVER executes tools, changes permissions, or invents facts.
    """
    def __init__(
        self,
        memory_manager: Optional[MemoryManager] = None,
        env_index: Optional[EnvironmentIndex] = None,
        tool_reg: Optional[ToolRegistry] = None,
        audit_logger: Optional[SQLiteAuditLogger] = None
    ):
        self.memory = memory_manager or MemoryManager()
        self.env_index = env_index or EnvironmentIndex()
        self.tool_registry = tool_reg or tool_registry
        self.audit_logger = audit_logger or SQLiteAuditLogger()

    def resolve(
        self,
        request: str,
        available_agents: Optional[Dict[str, str]] = None,
        project_root: Optional[str] = None
    ) -> StructuredIntent:
        """
        Resolves the user request into a deterministic StructuredIntent.
        """
        request_id = str(uuid.uuid4())
        root_dir = project_root or os.getcwd()
        
        observability_manager.emit_event(ObservabilityEvent(
            event_type="CONTEXT_RESOLUTION_STARTED",
            metadata={"request_id": request_id, "request": request}
        ))
        
        normalized = re.sub(r"[.!?]+$", "", request.strip().lower()).strip()
        evidence: List[str] = []
        ambiguity_reasons: List[str] = []
        ambiguity = False
        
        # 1. Ambiguity Detection (Phase 9)
        ambiguous_patterns = [
            r"^fix (the )?(app|project|it|bug|code)$",
            r"^update (the )?(app|project|it)$",
            r"^make it (faster|better|work)$",
            r"^do something$",
            r"^help( me)?$"
        ]
        for pat in ambiguous_patterns:
            if re.match(pat, normalized):
                ambiguity = True
                ambiguity_reasons.append(f"Request '{request}' lacks actionable entities or specific requirements.")
                
        if len(normalized.split()) <= 2 and normalized not in ("run tests", "check health", "start server"):
            ambiguity = True
            ambiguity_reasons.append("Request is too short to determine specific scope.")

        # 2. Environment Context & Conflict Precedence (Phase 4, 12, 13)
        env_knowledge = self.env_index.get_knowledge(root_dir)
        env_facts: Dict[str, Any] = {}
        if env_knowledge:
            env_facts = {
                "languages": [f.value for f in env_knowledge.languages],
                "frameworks": [f.value for f in env_knowledge.frameworks],
                "entry_points": [f.value for f in env_knowledge.entry_points],
                "timestamp": getattr(env_knowledge, "last_scanned", "")
            }
            evidence.append(f"EnvironmentIndex: languages={env_facts['languages']}, frameworks={env_facts['frameworks']}")
        else:
            evidence.append("EnvironmentIndex: No cached facts found for project root.")

        # 3. Memory Retrieval (Phase 5, 6)
        relevant_memories: List[Dict[str, Any]] = []
        relevant_procedures: List[Dict[str, Any]] = []
        procedure_match: Optional[Dict[str, Any]] = None
        
        try:
            if self.memory:
                # Episodic Memory
                ep_results = self.memory.get_relevant_context(request, memory_types=["episodic"], max_results=3)
                for ep in ep_results:
                    data = ep.get("data", {})
                    # Only accept verified memories
                    tags = data.get("tags", [])
                    if "verified" in tags and "unverified" not in tags:
                        # Conflict check with EnvironmentIndex (Precedence rule: Environment outranks old memory)
                        mem_summary = str(data.get("summary", "")).lower()
                        conflicted = False
                        if "django" in mem_summary and "fastapi" in str(env_facts.get("frameworks", [])).lower():
                            observability_manager.emit_event(ObservabilityEvent(
                                event_type="CONTEXT_CONFLICT",
                                metadata={"reason": "Episodic memory mentions Django but EnvironmentIndex detected FastAPI."}
                            ))
                            evidence.append("ConflictResolution: Ignored stale Django memory in favor of current FastAPI EnvironmentIndex.")
                            conflicted = True
                        if not conflicted:
                            relevant_memories.append(data)
                            evidence.append(f"EpisodicMemory: Found verified past event '{data.get('summary', '')[:60]}'")
                
                # Procedural Memory
                proc_results = self.memory.get_relevant_context(request, memory_types=["procedural"], max_results=2)
                for pr in proc_results:
                    p_data = pr.get("data", {})
                    relevant_procedures.append(p_data)
                    trigger = str(p_data.get("trigger", "")).lower()
                    if trigger and (trigger in normalized or normalized in trigger):
                        procedure_match = p_data
                        evidence.append(f"ProceduralMemory: Direct procedure match '{p_data.get('name')}' for trigger '{trigger}'")
        except Exception as e:
            evidence.append(f"MemoryResolutionWarning: {e}")

        # 4. Intent Classification (Phase 3)
        intent_type = IntentType.UNKNOWN
        entities = []
        requested_actions = []
        
        if ambiguity:
            intent_type = IntentType.UNKNOWN
        elif procedure_match:
            intent_type = IntentType.CODE_CHANGE if "code" in normalized else IntentType.SYSTEM_OPERATION
        elif any(w in normalized for w in ["research", "paper", "arxiv", "find papers", "literature"]):
            intent_type = IntentType.RESEARCH_TASK
        elif any(w in normalized for w in ["scan project", "refresh index", "query environment", "environment"]):
            intent_type = IntentType.ENVIRONMENT_QUERY
        elif any(w in normalized for w in ["remember", "procedure", "memorize", "learn"]):
            intent_type = IntentType.MEMORY_OPERATION
        elif any(w in normalized for w in ["cpu", "ram", "health", "system", "launch", "open app", "settings"]):
            intent_type = IntentType.SYSTEM_OPERATION
        elif any(w in normalized for w in ["delete", "remove file"]):
            intent_type = IntentType.FILE_OPERATION
        elif (any(w in normalized for w in ["api", "endpoint", "backend", "database", "sql", "server", "fastapi", "flask"]) and
              any(w in normalized for w in ["ui", "component", "frontend", "react", "css", "styling", "vite", "button"])):
            intent_type = IntentType.FULL_STACK_TASK
        elif any(w in normalized for w in ["api", "endpoint", "backend", "database", "sql", "server route", "pytest", "unit test"]):
            intent_type = IntentType.BACKEND_TASK
        elif any(w in normalized for w in ["ui", "component", "frontend", "react", "css", "styling", "vite", "page", "button", "dev server"]):
            intent_type = IntentType.FRONTEND_TASK
        elif any(w in normalized for w in ["write", "create", "edit", "implement", "refactor", "code"]):
            intent_type = IntentType.CODE_CHANGE
        elif any(w in normalized for w in ["search", "what is", "who is", "weather", "news", "tell me"]):
            intent_type = IntentType.INFORMATION_REQUEST
        else:
            intent_type = IntentType.UNKNOWN

        # Extract basic entities/actions
        for word in ["api", "endpoint", "component", "server", "database", "file", "test", "procedure"]:
            if word in normalized:
                entities.append(word)
        for act in ["create", "update", "delete", "run", "start", "stop", "read", "inspect", "search"]:
            if act in normalized:
                requested_actions.append(act)

        # 5. Candidate Agents & Tools Resolution (Phase 7, 8)
        candidate_agents: List[str] = []
        candidate_tools: List[str] = []
        
        if intent_type == IntentType.BACKEND_TASK:
            candidate_agents = ["BackendAgent"]
            evidence.append("AgentResolution: Backend keywords and capabilities matched BackendAgent.")
        elif intent_type == IntentType.FRONTEND_TASK:
            candidate_agents = ["FrontendAgent"]
            evidence.append("AgentResolution: Frontend keywords and UI capabilities matched FrontendAgent.")
        elif intent_type == IntentType.FULL_STACK_TASK or intent_type == IntentType.MIXED_TASK:
            candidate_agents = ["BackendAgent", "FrontendAgent"]
            evidence.append("AgentResolution: Full-stack requirements matched BackendAgent and FrontendAgent.")
        elif intent_type == IntentType.RESEARCH_TASK:
            candidate_agents = ["AcademicAgent"]
            evidence.append("AgentResolution: Research keywords matched AcademicAgent.")
        elif intent_type in (IntentType.SYSTEM_OPERATION, IntentType.FILE_OPERATION, IntentType.MEMORY_OPERATION):
            candidate_agents = ["SystemAgent", "DevAgent", "MasterAgent"]
            evidence.append(f"AgentResolution: {intent_type.value} matched SystemAgent.")
        elif intent_type == IntentType.INFORMATION_REQUEST:
            candidate_agents = ["MasterAgent", "SystemAgent"]
            evidence.append("AgentResolution: Information request matched MasterAgent.")
        else:
            candidate_agents = []

        # Filter candidate tools from Tool Registry
        for ag in candidate_agents:
            t_defs = self.tool_registry.get_for_agent(ag)
            for td in t_defs:
                if td.name not in candidate_tools:
                    candidate_tools.append(td.name)

        # 6. Confidence Scoring (Phase 10)
        confidence = ConfidenceLevel.MEDIUM
        score = 0.5
        
        if ambiguity:
            confidence = ConfidenceLevel.LOW
            score = 0.2
        elif intent_type != IntentType.UNKNOWN and len(candidate_agents) > 0:
            if env_facts and len(evidence) >= 2:
                confidence = ConfidenceLevel.HIGH
                score = 0.9
            else:
                confidence = ConfidenceLevel.MEDIUM
                score = 0.7
        else:
            confidence = ConfidenceLevel.LOW
            score = 0.3

        if ambiguity:
            observability_manager.emit_event(ObservabilityEvent(
                event_type="CONTEXT_AMBIGUOUS",
                metadata={"request": request, "reasons": ambiguity_reasons}
            ))

        intent = StructuredIntent(
            request_id=request_id,
            original_request=request,
            normalized_request=normalized,
            intent_type=intent_type,
            entities=entities,
            constraints=[],
            requested_actions=requested_actions,
            environment_context=env_facts,
            relevant_memories=relevant_memories,
            relevant_procedures=relevant_procedures,
            candidate_agents=candidate_agents,
            candidate_tools=candidate_tools,
            confidence=confidence,
            confidence_score=score,
            ambiguity=ambiguity,
            ambiguity_reasons=ambiguity_reasons,
            evidence=evidence,
            procedure_match=procedure_match,
            requires_clarification=ambiguity
        )

        observability_manager.emit_event(ObservabilityEvent(
            event_type="CONTEXT_RESOLUTION_COMPLETED",
            metadata={
                "request_id": request_id,
                "intent_type": intent.intent_type.value,
                "confidence": intent.confidence.value,
                "candidate_agents": intent.candidate_agents,
                "ambiguity": intent.ambiguity
            }
        ))

        return intent
