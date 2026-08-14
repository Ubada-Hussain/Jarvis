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

from core.llm_engine import LLMEngine
from core.memory_manager import MemoryManager
from core.audit_logger import SQLiteAuditLogger
from core.execution_gate import ExecutionGate, ToolMetadata, RiskLevel
from core.verification import ToolResult, VerificationStatus
from core.planner import TaskGraph, TaskNode, TaskState
from core.scheduler import DependencyScheduler
from core.a2a import A2ADispatcher, AgentMessage, MessageType, AgentStatus
from core.recovery import RecoveryManager, FailureCategory, RecoveryAction
from agents.backend_agent import BackendAgent
from agents.frontend_agent import FrontendAgent

class ScenarioApprovalManager:
    def __init__(self, auto_approve=True):
        self.auto_approve = auto_approve
        self.requested = False
        self.requested_action = ""

    def require_approval(self, action_desc: str) -> bool:
        self.requested = True
        self.requested_action = action_desc
        return self.auto_approve

class FlakyBackendAgent:
    """Simulates transient failures on attempt 1 and success on attempt 2."""
    def __init__(self, approval_manager, audit_logger):
        self.name = "BackendAgent"
        self.approval_manager = approval_manager
        self.audit_logger = audit_logger
        self.call_count = 0

    def execute(self, task: str, task_id: str = None) -> str:
        self.call_count += 1
        gate = ExecutionGate(self.approval_manager, agent_name=self.name, task_id=task_id, audit_logger=self.audit_logger)
        
        if self.call_count == 1:
            # First attempt fails transiently
            gate.register(ToolMetadata("flaky_server", RiskLevel.REVERSIBLE, "server_start"), lambda: ToolResult(
                status=VerificationStatus.VERIFIED_FAILURE,
                message="Port 8000 not open yet (transient lag)",
                evidence="Port check returned False"
            ))
            res = gate.execute("flaky_server")
            return res.message
        else:
            # Second attempt succeeds
            gate.register(ToolMetadata("flaky_server", RiskLevel.REVERSIBLE, "server_start"), lambda: ToolResult(
                status=VerificationStatus.VERIFIED_SUCCESS,
                message="Server started and port 8000 listening",
                evidence="Port check returned True on retry"
            ))
            res = gate.execute("flaky_server")
            return res.message

class PersistentFailAgent:
    """Consistently fails verification on every attempt."""
    def __init__(self, approval_manager, audit_logger):
        self.name = "BackendAgent"
        self.approval_manager = approval_manager
        self.audit_logger = audit_logger
        self.call_count = 0

    def execute(self, task: str, task_id: str = None) -> str:
        self.call_count += 1
        gate = ExecutionGate(self.approval_manager, agent_name=self.name, task_id=task_id, audit_logger=self.audit_logger)
        gate.register(ToolMetadata("broken_tool", RiskLevel.READ_ONLY, "misc"), lambda: ToolResult(
            status=VerificationStatus.VERIFIED_FAILURE,
            message="Database unreachable (persistent error)",
            evidence="Connection refused"
        ))
        res = gate.execute("broken_tool")
        return res.message

class UnverifiedAgent:
    """Returns UNVERIFIED output without verified proof."""
    def __init__(self, approval_manager, audit_logger):
        self.name = "BackendAgent"
        self.approval_manager = approval_manager
        self.audit_logger = audit_logger

    def execute(self, task: str, task_id: str = None) -> str:
        gate = ExecutionGate(self.approval_manager, agent_name=self.name, task_id=task_id, audit_logger=self.audit_logger)
        gate.register(ToolMetadata("unverified_action", RiskLevel.READ_ONLY, "misc"), lambda: "I think it is done")
        res = gate.execute("unverified_action")
        return res.message

def run_scenarios():
    print("=" * 65)
    print("  TASK 10 — REAL BEHAVIORAL FAILURE RECOVERY VERIFICATION")
    print("=" * 65)

    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db_file.name
    db_file.close()
    audit_logger = SQLiteAuditLogger(db_path)
    approval = ScenarioApprovalManager(auto_approve=True)

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO A: Recoverable Failure
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO A: Recoverable Failure (Transient -> Retry -> Verified Success) ---")
    flaky_agent = FlakyBackendAgent(approval, audit_logger)
    scheduler_a = DependencyScheduler({"BackendAgent": flaky_agent}, audit_logger)
    
    graph_a = TaskGraph(graph_id="g-scen-a", objective="Start Backend Server")
    node_a = TaskNode(
        node_id="n-scen-a",
        description="Start server with transient port lag",
        agent="BackendAgent",
        max_retries=2
    )
    graph_a.nodes = {node_a.node_id: node_a}
    
    summary_a = scheduler_a.execute_graph(graph_a)
    print(f"Graph summary: {summary_a}")
    print(f"Node A Final Status: {node_a.status}, Verification: {node_a.verification_status}, Attempts: {node_a.attempts}")
    
    assert node_a.status == TaskState.COMPLETED
    assert node_a.verification_status == "VERIFIED_SUCCESS"
    assert node_a.attempts == 2
    print("[PASS] Scenario A Passed: Transient failure recovered on retry with VERIFIED_SUCCESS.")

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO B: Persistent Failure
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO B: Persistent Failure (Retries Exhausted -> Failed) ---")
    persistent_agent = PersistentFailAgent(approval, audit_logger)
    scheduler_b = DependencyScheduler({"BackendAgent": persistent_agent}, audit_logger)
    
    graph_b = TaskGraph(graph_id="g-scen-b", objective="Connect to Broken Database")
    node_b = TaskNode(
        node_id="n-scen-b",
        description="Query unreachable database",
        agent="BackendAgent",
        max_retries=2
    )
    graph_b.nodes = {node_b.node_id: node_b}
    
    summary_b = scheduler_b.execute_graph(graph_b)
    print(f"Graph summary: {summary_b}")
    print(f"Node B Final Status: {node_b.status}, Verification: {node_b.verification_status}, Attempts: {node_b.attempts}")
    
    assert node_b.status == TaskState.FAILED
    assert node_b.verification_status == "VERIFIED_FAILURE"
    assert node_b.attempts == 2
    print("[PASS] Scenario B Passed: Persistent failure exhausted retries and terminated with FAILED.")

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO C: Permission Denial
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO C: Permission Denial (Non-Retryable -> Immediate Halt) ---")
    deny_approval = ScenarioApprovalManager(auto_approve=False)
    
    class PermissionAgent:
        def __init__(self, app_mgr, logger):
            self.name = "BackendAgent"
            self.approval_manager = app_mgr
            self.audit_logger = logger
            self.call_count = 0
        def execute(self, task: str, task_id: str = None) -> str:
            self.call_count += 1
            gate = ExecutionGate(self.approval_manager, agent_name=self.name, task_id=task_id, audit_logger=self.audit_logger)
            gate.register(ToolMetadata("drop_db", RiskLevel.DESTRUCTIVE, "db_admin", requires_confirmation=True), lambda: ToolResult(VerificationStatus.VERIFIED_SUCCESS, "Dropped"))
            res = gate.execute("drop_db")
            return res.message

    perm_agent = PermissionAgent(deny_approval, audit_logger)
    scheduler_c = DependencyScheduler({"BackendAgent": perm_agent}, audit_logger)
    
    graph_c = TaskGraph(graph_id="g-scen-c", objective="Drop Production Database")
    node_c = TaskNode(
        node_id="n-scen-c",
        description="Drop database with confirmation denied",
        agent="BackendAgent",
        risk_level="DESTRUCTIVE",
        max_retries=3
    )
    graph_c.nodes = {node_c.node_id: node_c}
    
    scheduler_c.execute_graph(graph_c)
    print(f"Node C Status: {node_c.status}, Verification: {node_c.verification_status}, Attempts: {node_c.attempts}")
    
    assert node_c.status == TaskState.BLOCKED
    assert node_c.attempts == 1 # Stoppped on first attempt without retry!
    assert deny_approval.requested is True
    print("[PASS] Scenario C Passed: Permission denial halted immediately without retrying.")

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO D: UNVERIFIED Result Handling
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO D: UNVERIFIED Result (Never Treated as Success) ---")
    unverified_agent = UnverifiedAgent(approval, audit_logger)
    scheduler_d = DependencyScheduler({"BackendAgent": unverified_agent}, audit_logger)
    
    graph_d = TaskGraph(graph_id="g-scen-d", objective="Run Unverified Tool")
    node_d = TaskNode(
        node_id="n-scen-d",
        description="Invoke unverified tool",
        agent="BackendAgent",
        max_retries=2
    )
    graph_d.nodes = {node_d.node_id: node_d}
    
    scheduler_d.execute_graph(graph_d)
    print(f"Node D Status: {node_d.status}, Verification: {node_d.verification_status}")
    
    assert node_d.status == TaskState.FAILED
    assert node_d.verification_status != "VERIFIED_SUCCESS"
    print("[PASS] Scenario D Passed: UNVERIFIED output never promoted to success.")

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO E: Downstream Dependency (Failure Blocks -> Recovery Unblocks)
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO E: Downstream Dependency Pipeline ---")
    
    # 1. Pipeline with persistent failure -> downstream BLOCKED
    p_agent = PersistentFailAgent(approval, audit_logger)
    good_fe_agent = FlakyBackendAgent(approval, audit_logger)
    good_fe_agent.name = "FrontendAgent"
    
    scheduler_e1 = DependencyScheduler({"BackendAgent": p_agent, "FrontendAgent": good_fe_agent}, audit_logger)
    graph_e1 = TaskGraph(graph_id="g-scen-e1", objective="Full Stack with Broken Backend")
    n_be = TaskNode(node_id="n-be-fail", description="Broken API", agent="BackendAgent", max_retries=2)
    n_fe = TaskNode(node_id="n-fe-wait", description="UI Integration", agent="FrontendAgent", dependencies=["n-be-fail"])
    graph_e1.nodes = {n_be.node_id: n_be, n_fe.node_id: n_fe}
    
    scheduler_e1.execute_graph(graph_e1)
    print(f"Pipe 1 - BE Status: {n_be.status}, FE Status: {n_fe.status}")
    assert n_be.status == TaskState.FAILED
    assert n_fe.status == TaskState.BLOCKED
    
    # 2. Pipeline with recoverable backend -> downstream proceeds to COMPLETED
    good_be = FlakyBackendAgent(approval, audit_logger)
    good_fe = FlakyBackendAgent(approval, audit_logger)
    good_fe.name = "FrontendAgent"
    
    scheduler_e2 = DependencyScheduler({"BackendAgent": good_be, "FrontendAgent": good_fe}, audit_logger)
    graph_e2 = TaskGraph(graph_id="g-scen-e2", objective="Full Stack with Recoverable Backend")
    n_be2 = TaskNode(node_id="n-be-rec", description="Recoverable API", agent="BackendAgent", max_retries=2)
    n_fe2 = TaskNode(node_id="n-fe-ok", description="UI Integration", agent="FrontendAgent", dependencies=["n-be-rec"], max_retries=2)
    graph_e2.nodes = {n_be2.node_id: n_be2, n_fe2.node_id: n_fe2}
    
    scheduler_e2.execute_graph(graph_e2)
    print(f"Pipe 2 - BE Status: {n_be2.status}, FE Status: {n_fe2.status}")
    assert n_be2.status == TaskState.COMPLETED
    assert n_fe2.status == TaskState.COMPLETED
    print("[PASS] Scenario E Passed: Upstream persistent failure blocks downstream; upstream recovery unblocks downstream.")

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO F: Audit Timeline Reconstruction
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO F: Audit Timeline Reconstruction ---")
    rec_events = audit_logger.query_recovery_events(task_id="g-scen-a")
    print(f"Recovery events for Scenario A: {len(rec_events)}")
    for ev in rec_events:
        print(f"  Attempt {ev['attempt']}: Category={ev['failure_category']}, Action={ev['recovery_action']}, Outcome={ev['outcome']}, Reason={ev['reason']}")
        
    assert len(rec_events) >= 2
    assert rec_events[0]["attempt"] == 1
    assert rec_events[0]["recovery_action"] in ("RETRY", "RECOVER")
    assert rec_events[1]["attempt"] == 2
    assert rec_events[1]["outcome"] == "VERIFIED_SUCCESS"
    print("[PASS] Scenario F Passed: Complete chronological recovery timeline reconstructable in SQLite.")

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
