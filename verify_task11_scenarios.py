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

from core.tool_registry import tool_registry, ToolDefinition
from core.execution_gate import ExecutionGate, ToolMetadata, RiskLevel
from core.verification import ToolResult, VerificationStatus
from core.audit_logger import SQLiteAuditLogger
from core.observability import observability_manager, ObservabilityEvent
from core.planner import TaskPlanner, TaskGraph, TaskNode, TaskState
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

class MockLLMEngine:
    def __init__(self, response="{}"):
        self.response = response
    def generate_response(self, prompt: str, system_prompt: str = None, tools: list = None, tool_logic=None):
        return self.response

def run_scenarios():
    print("=" * 65)
    print("  TASK 11 — REAL BEHAVIORAL TOOL REGISTRY & DISCOVERY")
    print("=" * 65)

    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db_file.name
    db_file.close()
    audit_logger = SQLiteAuditLogger(db_path)
    approval = ScenarioApprovalManager(auto_approve=True)

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO A: Valid Tool Execution
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO A: Valid Registered Tool Execution Pipeline ---")
    gate_a = ExecutionGate(approval, agent_name="BackendAgent", task_id="scen-a-task", audit_logger=audit_logger)
    gate_a.register(
        ToolMetadata("read_code_file", RiskLevel.READ_ONLY, "fs_read"),
        lambda file_path, start_line=1, end_line=10: ToolResult(
            VerificationStatus.VERIFIED_SUCCESS,
            f"Successfully read {file_path}",
            evidence="File lines verified on disk"
        )
    )
    
    res_a = gate_a.execute("read_code_file", file_path="core/system_tools.py", start_line=1, end_line=5)
    print(f"Tool Result Status: {res_a.status}, Message: {res_a.message}")
    
    events_a = audit_logger.query_events(task_id="scen-a-task")
    assert len(events_a) == 1
    assert events_a[0]["verification_status"] == "VERIFIED_SUCCESS"
    assert events_a[0]["permission_status"] == "GRANTED"
    assert res_a.status == VerificationStatus.VERIFIED_SUCCESS
    print("[PASS] Scenario A Passed: Registered tool executed, verified, and audited successfully.")

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO B: Unknown Tool (Hard Rejection)
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO B: Unknown / Unregistered Tool Rejection ---")
    captured_obs = []
    def obs_handler(e):
        captured_obs.append(e)
    observability_manager.register_callback(obs_handler)

    gate_b = ExecutionGate(approval, agent_name="MasterAgent", task_id="scen-b-task", audit_logger=audit_logger)
    res_b = gate_b.execute("magic_unregistered_tool", payload="dangerous_eval")
    print(f"Tool Result Status: {res_b.status}, Message: {res_b.message}")
    
    events_b = audit_logger.query_events(task_id="scen-b-task")
    assert len(events_b) == 1
    assert events_b[0]["execution_status"] == "REJECTED"
    assert events_b[0]["verification_status"] == "VERIFIED_FAILURE"
    assert "UNREGISTERED_TOOL" in res_b.message
    
    # Verify observability event exists
    rejected_events = [e.get("event", {}) for e in captured_obs if isinstance(e, dict) and e.get("event", {}).get("event_type") == "TOOL_REJECTED"]
    assert len(rejected_events) >= 1
    print("[PASS] Scenario B Passed: Unknown tool safely rejected before execution, audited, and emitted observability event.")

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO C: Invalid Tool Arguments (Pre-Execution Schema Failure)
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO C: Invalid Tool Arguments Validation ---")
    gate_c = ExecutionGate(approval, agent_name="BackendAgent", task_id="scen-c-task", audit_logger=audit_logger)
    executed_flag = {"executed": False}
    def mock_write(file_path, content):
        executed_flag["executed"] = True
        return ToolResult(VerificationStatus.VERIFIED_SUCCESS, "Wrote")
    gate_c.register(ToolMetadata("write_code_file", RiskLevel.REVERSIBLE, "fs_write"), mock_write)
    
    # 1. Missing required param
    res_c1 = gate_c.execute("write_code_file", file_path="main.py")
    assert res_c1.status == VerificationStatus.VERIFIED_FAILURE
    assert "INVALID_TOOL_ARGUMENTS" in res_c1.message
    assert executed_flag["executed"] is False
    print(f"Missing param check: {res_c1.message}")

    # 2. Wrong type
    res_c2 = gate_c.execute("write_code_file", file_path="main.py", content=9999)
    assert res_c2.status == VerificationStatus.VERIFIED_FAILURE
    assert "INVALID_TOOL_ARGUMENTS" in res_c2.message
    assert executed_flag["executed"] is False
    print(f"Wrong type check: {res_c2.message}")

    # 3. Unexpected parameter
    res_c3 = gate_c.execute("write_code_file", file_path="main.py", content="code", unauthorized_extra="hack")
    assert res_c3.status == VerificationStatus.VERIFIED_FAILURE
    assert "INVALID_TOOL_ARGUMENTS" in res_c3.message
    assert executed_flag["executed"] is False
    print(f"Unexpected param check: {res_c3.message}")
    print("[PASS] Scenario C Passed: Malformed arguments blocked before tool execution.")

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO D: Planner Capability & Tool Discovery
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO D: Planner Capability & Tool Discovery ---")
    # Backend task discovery
    be_tools = tool_registry.get_for_agent("BackendAgent")
    fe_tools = tool_registry.get_for_agent("FrontendAgent")
    
    print(f"BackendAgent Discovered Tools: {[t.name for t in be_tools]}")
    print(f"FrontendAgent Discovered Tools: {[t.name for t in fe_tools]}")
    
    assert any(t.name == "run_backend_tests" for t in be_tools)
    assert any(t.name == "start_frontend_server" for t in fe_tools)
    assert not any(t.name == "start_frontend_server" for t in be_tools)
    
    # Planner routing
    planner_json = '''{
        "nodes": [
            {"node_id": "n1", "description": "Create backend API", "agent": "BackendAgent", "dependencies": []},
            {"node_id": "n2", "description": "Create frontend UI", "agent": "FrontendAgent", "dependencies": ["n1"]}
        ]
    }'''
    planner = TaskPlanner(MockLLMEngine(planner_json))
    graph_d = planner.plan("Build Fullstack App")
    assert graph_d.nodes["n1"].agent == "BackendAgent"
    assert graph_d.nodes["n2"].agent == "FrontendAgent"
    assert graph_d.nodes["n2"].dependencies == ["n1"]
    print("[PASS] Scenario D Passed: Planner successfully discovered and mapped agent capabilities.")

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO E: Recovery Manager Registry Integration
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO E: Recovery Manager Registry Integration ---")
    rec_mgr = RecoveryManager()
    
    # Safe read tool lookup
    dec_read = rec_mgr.evaluate_recovery(
        category=FailureCategory.TIMEOUT,
        current_attempt=1,
        tool_name="read_code_file"
    )
    print(f"Read Tool Decision: Action={dec_read.action}, ShouldRetry={dec_read.should_retry}, MaxRetries={dec_read.max_retries}")
    assert dec_read.should_retry is True
    assert dec_read.action == RecoveryAction.RETRY
    assert dec_read.max_retries == 2

    # Destructive tool lookup
    dec_delete = rec_mgr.evaluate_recovery(
        category=FailureCategory.TOOL_ERROR,
        current_attempt=1,
        tool_name="delete_file"
    )
    print(f"Delete Tool Decision: Action={dec_delete.action}, ShouldRetry={dec_delete.should_retry}, MaxRetries={dec_delete.max_retries}")
    assert dec_delete.should_retry is False
    assert dec_delete.action == RecoveryAction.FAIL
    assert dec_delete.max_retries == 0
    print("[PASS] Scenario E Passed: RecoveryManager retrieves authoritative retry metadata from Tool Registry.")

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO F: Security — Destructive Tool Confirmation & Denial
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO F: Security Boundary (Destructive Tool Denial) ---")
    deny_approval = ScenarioApprovalManager(auto_approve=False)
    gate_f = ExecutionGate(deny_approval, agent_name="BackendAgent", task_id="scen-f-task", audit_logger=audit_logger)
    
    def mock_delete(file_path):
        return ToolResult(VerificationStatus.VERIFIED_SUCCESS, f"Deleted {file_path}")
    gate_f.register(ToolMetadata("delete_file", RiskLevel.DESTRUCTIVE, "fs_delete", requires_confirmation=True), mock_delete)
    
    res_f = gate_f.execute("delete_file", file_path="prod.db")
    print(f"Security Gate Result: Status={res_f.status}, Message={res_f.message}")
    
    events_f = audit_logger.query_events(task_id="scen-f-task")
    assert len(events_f) == 1
    assert events_f[0]["permission_status"] == "DENIED"
    assert events_f[0]["confirmation_status"] == "DENIED"
    assert res_f.status == VerificationStatus.VERIFIED_FAILURE
    assert deny_approval.requested is True
    print("[PASS] Scenario F Passed: Destructive tool denied by ExecutionGate despite valid registry metadata.")

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
