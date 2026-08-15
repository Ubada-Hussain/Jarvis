import os
import sys
import io
import time
import tempfile

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from core.approval import ApprovalManager, ApprovalStatus
from core.execution_gate import ExecutionGate, ToolMetadata, RiskLevel
from core.verification import ToolResult, VerificationStatus
from core.audit_logger import SQLiteAuditLogger
from core.session_state import SessionManager, SessionStatus
from core.a2a import AgentMessage, MessageType, AgentStatus
from core.planner import TaskNode, TaskState, TaskGraph
from core.scheduler import DependencyScheduler

def run_scenarios():
    print("=" * 65)
    print("  TASK 14 — REAL BEHAVIORAL APPROVAL & CONSENT SCENARIOS")
    print("=" * 65)

    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db_file.name
    db_file.close()
    
    audit_logger = SQLiteAuditLogger(db_path)
    approval_mgr = ApprovalManager(audit_logger=audit_logger, default_timeout_seconds=5)
    session_mgr = SessionManager(audit_logger=audit_logger, approval_manager=approval_mgr)

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO A: Level 0 / Low-Risk Safe Read-Only Execution
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO A: Low-Risk Safe Tool Execution ---")
    gate_a = ExecutionGate(approval_mgr, agent_name="SystemAgent", task_id="task-a", audit_logger=audit_logger)
    gate_a.register(ToolMetadata("read_file_safe", RiskLevel.READ_ONLY, "fs_read", requires_confirmation=False), lambda file_path: ToolResult(VerificationStatus.VERIFIED_SUCCESS, "Content read", evidence="Bytes: 42"))
    
    res_a = gate_a.execute("read_file_safe", session_id="sess-a", file_path="config.json")
    print(f"Scenario A Result: Status={res_a.status.name}, Message={res_a.message}")
    assert res_a.status == VerificationStatus.VERIFIED_SUCCESS
    print("[PASS] Scenario A: Safe read-only action executed without blocking on confirmation.")

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO B: Level 2 Action Requiring Explicit Approval
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO B: Level 2 Action Requiring Explicit Approval ---")
    gate_b = ExecutionGate(approval_mgr, agent_name="BackendAgent", task_id="task-b", audit_logger=audit_logger)
    gate_b.register(ToolMetadata("modify_db_schema", RiskLevel.EXTERNAL_SIDE_EFFECT, "db_write", requires_confirmation=True), lambda table: ToolResult(VerificationStatus.VERIFIED_SUCCESS, "Schema modified", evidence="ALTER TABLE executed"))
    
    # 1. Request approval
    req_b = approval_mgr.request_approval(
        session_id="sess-b",
        task_id="task-b",
        tool_name="modify_db_schema",
        risk_level=RiskLevel.EXTERNAL_SIDE_EFFECT,
        action_description="Alter users table to add email column"
    )
    print(f"Requested Approval: ID={req_b.approval_id}, Status={req_b.status.value}")
    assert req_b.status == ApprovalStatus.PENDING

    # 2. Grant approval
    approval_mgr.approve(req_b.approval_id, approved_by="DatabaseAdmin", reason="Schema change approved")
    print(f"Granted Approval: Status={approval_mgr.get(req_b.approval_id).status.value}")

    # 3. Execute through ExecutionGate
    res_b = gate_b.execute("modify_db_schema", approval_id=req_b.approval_id, session_id="sess-b", table="users")
    print(f"Scenario B Execution Result: Status={res_b.status.name}, Message={res_b.message}")
    assert res_b.status == VerificationStatus.VERIFIED_SUCCESS
    print("[PASS] Scenario B: Explicit approval requested, granted, and verified by ExecutionGate.")

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO C: Denial Prevents Execution
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO C: Explicit Denial Blocks Tool Execution ---")
    gate_c = ExecutionGate(approval_mgr, agent_name="BackendAgent", task_id="task-c", audit_logger=audit_logger)
    executed_c = {"ran": False}
    def dummy_destructive_tool():
        executed_c["ran"] = True
        return ToolResult(VerificationStatus.VERIFIED_SUCCESS, "Dropped")
    gate_c.register(ToolMetadata("drop_production_table", RiskLevel.DESTRUCTIVE, "db_admin", requires_confirmation=True), dummy_destructive_tool)
    
    req_c = approval_mgr.request_approval("sess-c", "task-c", "drop_production_table", RiskLevel.DESTRUCTIVE, "Drop table")
    approval_mgr.deny(req_c.approval_id, denied_by="SecOps", reason="Risk too high")
    
    res_c = gate_c.execute("drop_production_table", approval_id=req_c.approval_id, session_id="sess-c")
    print(f"Scenario C Result: Status={res_c.status.name}, Message={res_c.message}")
    assert res_c.status == VerificationStatus.VERIFIED_FAILURE
    assert not executed_c["ran"]
    print("[PASS] Scenario C: Denied action blocked at ExecutionGate; tool never executed.")

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO D: Expiration Blocks Execution
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO D: Expiration Invalidates Authorization ---")
    gate_d = ExecutionGate(approval_mgr, agent_name="BackendAgent", task_id="task-d", audit_logger=audit_logger)
    gate_d.register(ToolMetadata("sensitive_action", RiskLevel.EXTERNAL_SIDE_EFFECT, "admin", requires_confirmation=True), lambda: ToolResult(VerificationStatus.VERIFIED_SUCCESS, "Done"))
    
    req_d = approval_mgr.request_approval("sess-d", "task-d", "sensitive_action", RiskLevel.EXTERNAL_SIDE_EFFECT, "Quick action", timeout_seconds=1)
    approval_mgr.approve(req_d.approval_id)
    print("Waiting 1.2s for approval TTL expiration...")
    time.sleep(1.2)
    
    res_d = gate_d.execute("sensitive_action", approval_id=req_d.approval_id, session_id="sess-d")
    print(f"Scenario D Result: Status={res_d.status.name}, Message={res_d.message}")
    assert res_d.status == VerificationStatus.VERIFIED_FAILURE
    assert "EXPIRED" in res_d.message or "APPROVAL_BLOCKED" in res_d.message
    print("[PASS] Scenario D: Expired approval was properly rejected by ExecutionGate.")

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO E: Scope Isolation (Cross-Session, Cross-Task, Cross-Tool)
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO E: Scope Binding Rejections ---")
    req_e = approval_mgr.request_approval(
        session_id="session-ALPHA",
        task_id="task-ALPHA",
        tool_name="tool_ALPHA",
        risk_level=RiskLevel.EXTERNAL_SIDE_EFFECT,
        action_description="Action Alpha",
        node_id="node-ALPHA"
    )
    approval_mgr.approve(req_e.approval_id)
    
    # 1. Wrong Session
    v1, m1 = approval_mgr.is_valid(req_e.approval_id, "session-BETA", "task-ALPHA", "tool_ALPHA", "node-ALPHA")
    assert not v1
    # 2. Wrong Task
    v2, m2 = approval_mgr.is_valid(req_e.approval_id, "session-ALPHA", "task-BETA", "tool_ALPHA", "node-ALPHA")
    assert not v2
    # 3. Wrong Tool
    v3, m3 = approval_mgr.is_valid(req_e.approval_id, "session-ALPHA", "task-ALPHA", "tool_BETA", "node-ALPHA")
    assert not v3
    # 4. Wrong Node
    v4, m4 = approval_mgr.is_valid(req_e.approval_id, "session-ALPHA", "task-ALPHA", "tool_ALPHA", "node-BETA")
    assert not v4
    print(f"Scope Mismatch Rejections: Session={m1}, Task={m2}, Tool={m3}, Node={m4}")
    print("[PASS] Scenario E: Strict 4-way scope binding verified.")

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO F: Recovery & Fresh Approval on Changed Action
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO F: Recovery & Escalated Action Rules ---")
    req_f1 = approval_mgr.request_approval("sess-f", "task-f", "write_file", RiskLevel.REVERSIBLE, "Write temp file", timeout_seconds=100)
    approval_mgr.approve(req_f1.approval_id)
    
    # Valid retry of same action
    valid_retry, _ = approval_mgr.is_valid(req_f1.approval_id, "sess-f", "task-f", "write_file")
    assert valid_retry
    
    # Changed tool / escalated risk requires fresh approval
    req_f2 = approval_mgr.request_approval("sess-f", "task-f", "delete_all", RiskLevel.DESTRUCTIVE, "Delete all files")
    assert req_f2.status == ApprovalStatus.PENDING
    assert req_f2.approval_id != req_f1.approval_id
    print(f"Fresh Approval required for escalated tool: Status={req_f2.status.value}")
    print("[PASS] Scenario F: Safe retries allowed; changed/escalated actions require fresh approval.")

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO G: Session Cancellation Invalidates Pending Approvals
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO G: Session Cancellation Invalidates Approvals ---")
    sess_g = session_mgr.create_session(initial_request="Cancelling task")
    req_g = approval_mgr.request_approval(sess_g.session_id, "task-g", "reboot_node", RiskLevel.DESTRUCTIVE, "Reboot server")
    assert req_g.status == ApprovalStatus.PENDING
    
    session_mgr.cancel_session(sess_g.session_id, reason="User interrupted via UI")
    updated_g = approval_mgr.get(req_g.approval_id)
    print(f"Approval status after session cancellation: {updated_g.status.value}")
    assert updated_g.status == ApprovalStatus.CANCELLED
    print("[PASS] Scenario G: Active approvals cleanly cancelled upon session cancellation.")

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO H: Application Restart Persistence Recovery
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO H: Application Restart State Reload ---")
    req_h = approval_mgr.request_approval("sess-h", "task-h", "deploy_cluster", RiskLevel.EXTERNAL_SIDE_EFFECT, "Deploy cluster")
    approval_mgr.approve(req_h.approval_id, approved_by="InfraLead", reason="Infra greenlit")
    
    # Simulate restart with fresh ApprovalManager connected to same DB
    restarted_mgr = ApprovalManager(audit_logger=audit_logger)
    reloaded_h = restarted_mgr.get(req_h.approval_id)
    print(f"Reloaded Approval: Status={reloaded_h.status.value}, ApprovedBy={reloaded_h.approved_by}")
    assert reloaded_h.status == ApprovalStatus.APPROVED
    assert reloaded_h.approved_by == "InfraLead"
    print("[PASS] Scenario H: Approval state faithfully persisted and reloaded after restart.")

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO I: A2A Structured Approval Correlation
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO I: A2A Approval Correlation ---")
    req_i = approval_mgr.request_approval("sess-i", "task-i", "write_code_file", RiskLevel.EXTERNAL_SIDE_EFFECT, "Write code", node_id="node-i")
    approval_mgr.approve(req_i.approval_id)
    
    a2a_msg = AgentMessage(
        message_id="msg-a2a-1",
        session_id="sess-i",
        task_id="task-i",
        node_id="node-i",
        approval_id=req_i.approval_id,
        sender_agent="Scheduler",
        recipient_agent="BackendAgent",
        message_type=MessageType.TASK_REQUEST,
        status=AgentStatus.PENDING
    )
    
    # Recipient uses approval_id in ExecutionGate
    gate_i = ExecutionGate(approval_mgr, agent_name="BackendAgent", task_id=a2a_msg.task_id, audit_logger=audit_logger)
    gate_i.register(ToolMetadata("write_code_file", RiskLevel.EXTERNAL_SIDE_EFFECT, "fs_perm", requires_confirmation=True), lambda file_path, content: ToolResult(VerificationStatus.VERIFIED_SUCCESS, "Code written"))
    
    res_i = gate_i.execute("write_code_file", approval_id=a2a_msg.approval_id, session_id=a2a_msg.session_id, node_id=a2a_msg.node_id, file_path="api.py", content="print('hello')")
    print(f"A2A Execution Result: Status={res_i.status.name}, Message={res_i.message}")
    assert res_i.status == VerificationStatus.VERIFIED_SUCCESS
    print("[PASS] Scenario I: A2A message carried approval reference and passed gate verification.")

    # Clean up
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass

    print("\n" + "=" * 65)
    print("  ALL 9 REAL BEHAVIORAL APPROVAL SCENARIOS PASSED!")
    print("=" * 65)

if __name__ == "__main__":
    run_scenarios()
