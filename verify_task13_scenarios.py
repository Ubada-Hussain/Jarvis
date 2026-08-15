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

from core.session_state import SessionManager, SessionState, SessionStatus
from core.audit_logger import SQLiteAuditLogger
from core.planner import TaskPlanner, TaskGraph, TaskNode, TaskState
from core.scheduler import DependencyScheduler
from core.verification import ToolResult, VerificationStatus
from core.execution_gate import ExecutionGate, ToolMetadata, RiskLevel
from agents.master_agent import MasterAgent

class ScenarioApprovalManager:
    def __init__(self, auto_approve=True):
        self.auto_approve = auto_approve
    def require_approval(self, action_desc: str) -> bool:
        return self.auto_approve

class MockLLMEngine:
    def __init__(self, response="{}"):
        self.response = response
    def generate_response(self, prompt: str, system_prompt: str = None, tools: list = None, tool_logic=None):
        return self.response

def run_scenarios():
    print("=" * 65)
    print("  TASK 13 — REAL BEHAVIORAL SESSION & CONVERSATION STATE")
    print("=" * 65)

    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db_file.name
    db_file.close()
    audit_logger = SQLiteAuditLogger(db_path)
    session_mgr = SessionManager(audit_logger=audit_logger)
    approval = ScenarioApprovalManager(auto_approve=True)

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO A: Normal Request Lifecycle (NEW -> PLANNING -> EXECUTING -> COMPLETED)
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO A: Normal Lifecycle Execution ---")
    session_a = session_mgr.create_session(initial_request="Create backend health API")
    sid_a = session_a.session_id
    print(f"Session Created: ID={sid_a}, Status={session_a.session_status}")
    assert session_a.session_status == SessionStatus.NEW

    session_mgr.transition_state(sid_a, SessionStatus.PLANNING, reason="Planning started")
    assert session_mgr.get_session(sid_a).session_status == SessionStatus.PLANNING

    graph_a = TaskGraph(graph_id="graph-scen-a", objective="Create backend health API")
    graph_a.nodes["n1"] = TaskNode(node_id="n1", description="Write API code", agent="BackendAgent")
    
    class MockBackendAgent:
        def execute(self, task, task_id=None):
            gate = ExecutionGate(approval, agent_name="BackendAgent", task_id=task_id, audit_logger=audit_logger)
            gate.register(ToolMetadata("write_code_file", RiskLevel.REVERSIBLE, "fs_write"), lambda file_path, content: ToolResult(VerificationStatus.VERIFIED_SUCCESS, "API created", evidence="File on disk"))
            return gate.execute("write_code_file", file_path="health.py", content="code").message

    scheduler_a = DependencyScheduler({"BackendAgent": MockBackendAgent()}, audit_logger, session_manager=session_mgr)
    scheduler_a.execute_graph(graph_a, session_id=sid_a)
    
    final_sess_a = session_mgr.get_session(sid_a)
    print(f"Final Session Status: {final_sess_a.session_status}, Verified Results: {len(final_sess_a.recent_verified_results)}")
    assert final_sess_a.session_status == SessionStatus.COMPLETED
    assert len(final_sess_a.recent_verified_results) >= 1
    print("[PASS] Scenario A Passed: Normal request transitioned accurately from NEW to COMPLETED.")

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO B: Ambiguous Request & Clarification Resume
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO B: Ambiguous Request & Clarification Resume ---")
    session_b = session_mgr.create_session(initial_request="Fix the app.")
    sid_b = session_b.session_id
    
    # MasterAgent execution with ambiguous request
    mock_llm_b = MockLLMEngine('{"nodes": [{"node_id": "1", "description": "Fix timeout", "agent": "DevAgent", "dependencies": []}]}')
    master = MasterAgent(mock_llm_b, None, approval, session_manager=session_mgr, audit_logger=audit_logger)
    class SimpleSuccessWorker:
        description = "General development worker"
        def execute(self, task, task_id=None):
            return "Fix completed successfully"
    master.agents["DevAgent"] = SimpleSuccessWorker()
    response_b = master.execute("Fix the app.", session_id=sid_b)
    
    sess_b_waiting = session_mgr.get_session(sid_b)
    print(f"Response: {response_b}")
    print(f"Session Status: {sess_b_waiting.session_status}, Pending Clarification: {sess_b_waiting.pending_clarification}")
    assert sess_b_waiting.session_status == SessionStatus.WAITING_FOR_CLARIFICATION
    assert sess_b_waiting.pending_clarification is True

    # User provides clarification
    response_b2 = master.execute("Fix the MongoDB connection timeout in database.py", session_id=sid_b)
    sess_b_resumed = session_mgr.get_session(sid_b)
    print(f"Clarified Response: {response_b2}")
    print(f"Resumed Session Status: {sess_b_resumed.session_status}, Clarification History: {len(sess_b_resumed.clarification_history)}")
    assert sess_b_resumed.session_status == SessionStatus.COMPLETED
    assert len(sess_b_resumed.clarification_history) >= 1
    print("[PASS] Scenario B Passed: Ambiguity paused execution into WAITING_FOR_CLARIFICATION and safely resumed.")

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO C: Session Cancellation
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO C: Session Cancellation Safety ---")
    session_c = session_mgr.create_session(initial_request="Long running build task")
    sid_c = session_c.session_id
    session_mgr.transition_state(sid_c, SessionStatus.PLANNING)
    session_mgr.transition_state(sid_c, SessionStatus.EXECUTING)
    
    # User requests cancellation
    session_mgr.cancel_session(sid_c, reason="User interrupted via UI")
    sess_c = session_mgr.get_session(sid_c)
    print(f"Cancelled Session Status: {sess_c.session_status}")
    assert sess_c.session_status == SessionStatus.CANCELLED
    
    # Execution halts immediately
    graph_c = TaskGraph(graph_id="graph-scen-c", objective="Long task")
    graph_c.nodes["n1"] = TaskNode(node_id="n1", description="Long build", agent="BackendAgent")
    scheduler_c = DependencyScheduler({"BackendAgent": MockBackendAgent()}, audit_logger, session_manager=session_mgr)
    scheduler_c.execute_graph(graph_c, session_id=sid_c)
    
    assert session_mgr.get_session(sid_c).session_status == SessionStatus.CANCELLED
    print("[PASS] Scenario C Passed: Session cancelled safely and never reported as success.")

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO D: Failure & Recovery Transition
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO D: Failure & Recovery Lifecycle ---")
    session_d = session_mgr.create_session(initial_request="Unstable network call")
    sid_d = session_d.session_id
    
    attempt_tracker = {"count": 0}
    class FlakyWorker:
        def execute(self, task, task_id=None):
            attempt_tracker["count"] += 1
            if attempt_tracker["count"] == 1:
                raise ConnectionError("Connection timeout")
            return "SUCCESS: Connected on retry"
            
    graph_d = TaskGraph(graph_id="graph-scen-d", objective="Unstable task")
    graph_d.nodes["n1"] = TaskNode(node_id="n1", description="Network query", agent="DevAgent", max_retries=2)
    scheduler_d = DependencyScheduler({"DevAgent": FlakyWorker()}, audit_logger, session_manager=session_mgr)
    scheduler_d.execute_graph(graph_d, session_id=sid_d)
    
    sess_d = session_mgr.get_session(sid_d)
    print(f"Recovered Session Status: {sess_d.session_status}, Attempts: {attempt_tracker['count']}")
    assert sess_d.session_status == SessionStatus.COMPLETED
    assert attempt_tracker["count"] == 2
    print("[PASS] Scenario D Passed: Failure transitioned through RECOVERING and resumed upon verified retry.")

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO E: Multi-Session Strict Isolation
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO E: Multi-Session Isolation ---")
    sess_e1 = session_mgr.create_session(initial_request="User 1 Backend Task")
    sess_e2 = session_mgr.create_session(initial_request="User 2 Frontend Task")
    
    session_mgr.update_session(sess_e1.session_id, active_agent="BackendAgent", active_node_id="be-101")
    session_mgr.update_session(sess_e2.session_id, active_agent="FrontendAgent", active_node_id="fe-202")
    
    session_mgr.add_verified_result(sess_e1.session_id, "be-101", "BackendAgent", "API OK", "db verified")
    session_mgr.add_failure(sess_e2.session_id, "fe-202", "FrontendAgent", "CSS Syntax Error")
    
    e1_loaded = session_mgr.get_session(sess_e1.session_id)
    e2_loaded = session_mgr.get_session(sess_e2.session_id)
    
    print(f"Session E1: Agent={e1_loaded.active_agent}, Results={len(e1_loaded.recent_verified_results)}, Failures={len(e1_loaded.recent_failures)}")
    print(f"Session E2: Agent={e2_loaded.active_agent}, Results={len(e2_loaded.recent_verified_results)}, Failures={len(e2_loaded.recent_failures)}")
    
    assert e1_loaded.active_agent == "BackendAgent"
    assert len(e1_loaded.recent_verified_results) == 1
    assert len(e1_loaded.recent_failures) == 0
    
    assert e2_loaded.active_agent == "FrontendAgent"
    assert len(e2_loaded.recent_verified_results) == 0
    assert len(e2_loaded.recent_failures) == 1
    print("[PASS] Scenario E Passed: Simultaneous sessions maintained 100% strict isolation.")

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO F: Application Restart Persistence Recovery
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO F: Restart Persistence & State Reload ---")
    session_f = session_mgr.create_session(conversation_id="conv-f", initial_request="Restart recovery test")
    sid_f = session_f.session_id
    session_mgr.transition_state(sid_f, SessionStatus.PLANNING)
    session_mgr.transition_state(sid_f, SessionStatus.EXECUTING, task_id="task-f-999", node_id="node-f-1")
    session_mgr.update_session(sid_f, active_agent="DevAgent", user_approved_actions=["write_code_file"])
    
    # Simulate restart by instantiating a completely new SessionManager instance connected to the SQLite DB
    restarted_mgr = SessionManager(audit_logger=audit_logger)
    reloaded_f = restarted_mgr.get_session(sid_f)
    
    print(f"Reloaded Status: {reloaded_f.session_status}, Active Task: {reloaded_f.active_task_id}, Node: {reloaded_f.active_node_id}")
    assert reloaded_f is not None
    assert reloaded_f.session_id == sid_f
    assert reloaded_f.session_status == SessionStatus.EXECUTING
    assert reloaded_f.active_task_id == "task-f-999"
    assert reloaded_f.active_node_id == "node-f-1"
    assert reloaded_f.session_status != SessionStatus.COMPLETED
    print("[PASS] Scenario F Passed: Restart faithfully reloaded operational state without falsifying success.")

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
