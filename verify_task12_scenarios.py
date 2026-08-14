import os
import sys
import io
import time
import uuid
import tempfile

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from core.context_resolver import ContextResolver, StructuredIntent, IntentType, ConfidenceLevel
from core.environment_index import EnvironmentIndex
from core.environment_models import EnvironmentKnowledge, EnvironmentFact
from core.memory_manager import MemoryManager
from core.memory_models import EpisodicMemory, ProceduralMemory, ProcedureStep
from core.tool_registry import tool_registry
from core.planner import TaskPlanner, TaskGraph, TaskNode, TaskState
from core.execution_gate import ExecutionGate, ToolMetadata, RiskLevel
from core.verification import ToolResult, VerificationStatus
from core.audit_logger import SQLiteAuditLogger
from core.scheduler import DependencyScheduler

class ScenarioApprovalManager:
    def __init__(self, auto_approve=True):
        self.auto_approve = auto_approve
        self.requested = False
        self.requested_action = ""

    def require_approval(self, action_desc: str) -> bool:
        self.requested = True
        self.requested_action = action_desc
        return self.auto_approve

class MockMemory:
    def __init__(self):
        self.memories = []
        self.procedures = []
    def get_relevant_context(self, query: str, memory_types: list = None, max_results: int = 3):
        res = []
        if not memory_types or "episodic" in memory_types:
            for m in self.memories:
                res.append({"data": m, "score": 0.8})
        if not memory_types or "procedural" in memory_types:
            for p in self.procedures:
                res.append({"data": p, "score": 0.95})
        return res

class MockEnvIndex:
    def __init__(self, frameworks=None, languages=None):
        self.knowledge = EnvironmentKnowledge(
            project_root=os.getcwd(),
            environment_id="env-scen",
            platform="win32",
            os="Windows",
            architecture="x64",
            languages=[EnvironmentFact(fact="language", value=l) for l in (languages or ["Python"])],
            frameworks=[EnvironmentFact(fact="framework", value=f) for f in (frameworks or ["FastAPI"])],
            entry_points=[EnvironmentFact(fact="entry_point", value="main.py")]
        )
    def get_knowledge(self, project_root: str):
        return self.knowledge

class MockLLMEngine:
    def __init__(self, response_map=None):
        self.response_map = response_map or {}
    def generate_response(self, prompt: str, system_prompt: str = None, tools: list = None, tool_logic=None):
        for k, v in self.response_map.items():
            if k in prompt:
                return v
        return '{"nodes": []}'

def run_scenarios():
    print("=" * 65)
    print("  TASK 12 — REAL BEHAVIORAL CONTEXT & INTENT RESOLUTION")
    print("=" * 65)

    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db_file.name
    db_file.close()
    audit_logger = SQLiteAuditLogger(db_path)
    approval = ScenarioApprovalManager(auto_approve=True)
    mock_memory = MockMemory()
    mock_env = MockEnvIndex()

    resolver = ContextResolver(
        memory_manager=mock_memory,
        env_index=mock_env,
        tool_reg=tool_registry,
        audit_logger=audit_logger
    )

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO A: Backend Intent Resolution & Safe Pipeline Execution
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO A: Backend Context Resolution & Pipeline Execution ---")
    intent_a = resolver.resolve("Create a backend API route for items")
    print(f"Intent Type: {intent_a.intent_type}, Candidate Agents: {intent_a.candidate_agents}, Confidence: {intent_a.confidence}")
    assert intent_a.intent_type == IntentType.BACKEND_TASK
    assert "BackendAgent" in intent_a.candidate_agents
    assert intent_a.confidence == ConfidenceLevel.HIGH

    # Planner constructs graph
    llm_a = MockLLMEngine({"items": '{"nodes": [{"node_id": "be-1", "description": "Write API code", "agent": "BackendAgent", "dependencies": []}]}'})
    planner_a = TaskPlanner(llm_a)
    graph_a = planner_a.plan(intent_a)
    assert len(graph_a.nodes) == 1
    assert graph_a.nodes["be-1"].agent == "BackendAgent"

    # Execution through ExecutionGate & Verification
    class MockBackendWorker:
        def execute(self, task, task_id=None):
            gate = ExecutionGate(approval, agent_name="BackendAgent", task_id=task_id, audit_logger=audit_logger)
            gate.register(ToolMetadata("write_code_file", RiskLevel.REVERSIBLE, "fs_write"), lambda file_path, content: ToolResult(VerificationStatus.VERIFIED_SUCCESS, "API created", evidence="File on disk"))
            return gate.execute("write_code_file", file_path="api.py", content="route code").message

    scheduler_a = DependencyScheduler({"BackendAgent": MockBackendWorker()}, audit_logger)
    scheduler_a.execute_graph(graph_a)
    assert graph_a.nodes["be-1"].status == TaskState.COMPLETED
    assert graph_a.nodes["be-1"].verification_status == "VERIFIED_SUCCESS"
    print("[PASS] Scenario A Passed: Backend intent resolved, planned, and verified via ExecutionGate.")

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO B: Frontend Intent Resolution
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO B: Frontend Context Resolution ---")
    intent_b = resolver.resolve("Build a React button component with CSS styling")
    print(f"Intent Type: {intent_b.intent_type}, Candidate Agents: {intent_b.candidate_agents}, Confidence: {intent_b.confidence}")
    assert intent_b.intent_type == IntentType.FRONTEND_TASK
    assert "FrontendAgent" in intent_b.candidate_agents
    assert intent_b.confidence == ConfidenceLevel.HIGH
    print("[PASS] Scenario B Passed: Frontend intent accurately resolved.")

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO C: Full-Stack Resolution & Dependency Graph
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO C: Full-Stack Resolution & Dependency Graph ---")
    intent_c = resolver.resolve("Add backend user endpoint and connect frontend UI button")
    print(f"Intent Type: {intent_c.intent_type}, Candidates: {intent_c.candidate_agents}")
    assert intent_c.intent_type == IntentType.FULL_STACK_TASK
    assert "BackendAgent" in intent_c.candidate_agents
    assert "FrontendAgent" in intent_c.candidate_agents

    llm_c = MockLLMEngine({
        "backend": '{"nodes": [{"node_id": "be-api", "description": "Create user API", "agent": "BackendAgent", "dependencies": []}, {"node_id": "fe-ui", "description": "Create UI button", "agent": "FrontendAgent", "dependencies": ["be-api"]}]}'
    })
    planner_c = TaskPlanner(llm_c)
    graph_c = planner_c.plan(intent_c)
    assert len(graph_c.nodes) == 2
    assert graph_c.nodes["fe-ui"].dependencies == ["be-api"]
    print("[PASS] Scenario C Passed: Full-stack intent resolved into ordered multi-agent TaskGraph.")

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO D: Ambiguous Request ("Fix the app")
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO D: Ambiguity Detection & Safe Handling ---")
    intent_d = resolver.resolve("Fix the app.")
    print(f"Ambiguity: {intent_d.ambiguity}, Reasons: {intent_d.ambiguity_reasons}, Requires Clarification: {intent_d.requires_clarification}")
    assert intent_d.ambiguity is True
    assert intent_d.requires_clarification is True
    assert intent_d.confidence == ConfidenceLevel.LOW

    planner_d = TaskPlanner(MockLLMEngine())
    graph_d = planner_d.plan(intent_d)
    assert len(graph_d.nodes) == 1
    clarify_node = list(graph_d.nodes.values())[0]
    assert "Clarification required" in clarify_node.description
    assert clarify_node.risk_level == "READ_ONLY"
    print("[PASS] Scenario D Passed: Ambiguous request halted safely with clarification node without executing risky ops.")

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO E: Procedural Memory Match Resolution
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO E: Procedural Memory Match Resolution ---")
    mock_memory.procedures.append({
        "name": "DeployFrontendUI",
        "procedure_id": "proc-deploy-ui",
        "trigger": "deploy frontend UI",
        "steps": [
            {"agent": "FrontendAgent", "action": "run_frontend_build", "description": "Build UI bundle"},
            {"agent": "FrontendAgent", "action": "start_frontend_server", "description": "Start production server"}
        ]
    })
    intent_e = resolver.resolve("deploy frontend UI")
    print(f"Procedure Match: {intent_e.procedure_match is not None}")
    assert intent_e.procedure_match is not None
    assert intent_e.procedure_match["name"] == "DeployFrontendUI"

    planner_e = TaskPlanner(MockLLMEngine())
    graph_e = planner_e.plan(intent_e)
    assert len(graph_e.nodes) == 2
    assert "proc-deploy-ui-step-0" in graph_e.nodes
    assert "proc-deploy-ui-step-1" in graph_e.nodes
    assert graph_e.nodes["proc-deploy-ui-step-1"].dependencies == ["proc-deploy-ui-step-0"]
    print("[PASS] Scenario E Passed: Procedural memory matched and instantiated into verified TaskGraph.")

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO F: Conflicting Context (Environment Wins Over Stale Memory)
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO F: Precedence & Conflicting Context Resolution ---")
    mock_memory.memories.append({
        "summary": "Old memory says project framework is Django",
        "tags": ["verified"]
    })
    # Environment index reports FastAPI
    intent_f = resolver.resolve("Create API endpoint")
    print(f"Environment Frameworks: {intent_f.environment_context.get('frameworks')}")
    print(f"Relevant Memories: {len(intent_f.relevant_memories)}")
    
    assert "FastAPI" in intent_f.environment_context.get("frameworks", [])
    # Django memory was discarded by conflict precedence rule
    assert len(intent_f.relevant_memories) == 0
    assert any("ConflictResolution" in ev for ev in intent_f.evidence)
    print("[PASS] Scenario F Passed: Current EnvironmentIndex outranks stale conflicting episodic memory.")

    # Clean up
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass

    print("\n" + "=" * 65)
    print("  ALL 6 REAL BEHAVIORAL SCENARIOS COMPLETED SUCCESSFULLY!")
    print("=" * 65)

if __name__ == "__main__":
    run_scenarios()
