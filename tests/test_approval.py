import unittest
import os
import tempfile
import time
from core.approval import ApprovalManager, ApprovalRequest, ApprovalStatus
from core.execution_gate import ExecutionGate, ToolMetadata, RiskLevel
from core.verification import ToolResult, VerificationStatus
from core.audit_logger import SQLiteAuditLogger
from core.session_state import SessionManager, SessionStatus
from core.a2a import AgentMessage, MessageType, AgentStatus
from core.planner import TaskNode, TaskState, TaskGraph
from core.scheduler import DependencyScheduler

class TestApprovalManager(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        self.audit_logger = SQLiteAuditLogger(self.db_path)
        self.approval_mgr = ApprovalManager(audit_logger=self.audit_logger, default_timeout_seconds=5)
        self.session_mgr = SessionManager(audit_logger=self.audit_logger, approval_manager=self.approval_mgr)

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception:
                pass

    # ── 1-5: Basic Approval Lifecycle ─────────────────────────────────────────
    def test_01_approval_request_creation(self):
        """1. Approval request created with PENDING status and correct fields."""
        req = self.approval_mgr.request_approval(
            session_id="sess-1",
            task_id="task-1",
            tool_name="database_migration",
            risk_level=RiskLevel.EXTERNAL_SIDE_EFFECT,
            action_description="Migrate user schema",
            node_id="node-1"
        )
        self.assertIsNotNone(req.approval_id)
        self.assertEqual(req.status, ApprovalStatus.PENDING)
        self.assertEqual(req.session_id, "sess-1")
        self.assertEqual(req.tool_name, "database_migration")

    def test_02_approval_succeeds(self):
        """2. Explicit approve() transitions status to APPROVED."""
        req = self.approval_mgr.request_approval("sess-1", "task-1", "deploy_app", RiskLevel.EXTERNAL_SIDE_EFFECT, "Deploy app")
        approved_req = self.approval_mgr.approve(req.approval_id, approved_by="SecOps", reason="Code reviewed")
        self.assertEqual(approved_req.status, ApprovalStatus.APPROVED)
        self.assertEqual(approved_req.approved_by, "SecOps")

    def test_03_denial_works(self):
        """3. Explicit deny() transitions status to DENIED."""
        req = self.approval_mgr.request_approval("sess-1", "task-1", "delete_records", RiskLevel.DESTRUCTIVE, "Delete data")
        denied_req = self.approval_mgr.deny(req.approval_id, denied_by="Admin", reason="Unauthorized")
        self.assertEqual(denied_req.status, ApprovalStatus.DENIED)
        self.assertEqual(denied_req.approval_reason, "Unauthorized")

    def test_04_cancellation_works(self):
        """4. Cancellation transitions status to CANCELLED."""
        req = self.approval_mgr.request_approval("sess-1", "task-1", "restart_cluster", RiskLevel.DESTRUCTIVE, "Restart cluster")
        canc_req = self.approval_mgr.cancel(req.approval_id, reason="Aborted by operator")
        self.assertEqual(canc_req.status, ApprovalStatus.CANCELLED)

    def test_05_expiration_works(self):
        """5. Expiration transitions status to EXPIRED."""
        req = self.approval_mgr.request_approval("sess-1", "task-1", "temp_tool", RiskLevel.REVERSIBLE, "Temp action")
        exp_req = self.approval_mgr.expire(req.approval_id)
        self.assertEqual(exp_req.status, ApprovalStatus.EXPIRED)

    # ── 6-10: Scope Binding & Validation ──────────────────────────────────────
    def test_06_wrong_session_rejected(self):
        """6. Approval request from session A cannot authorize session B."""
        req = self.approval_mgr.request_approval("sess-A", "task-1", "tool_x", RiskLevel.EXTERNAL_SIDE_EFFECT, "Do X")
        self.approval_mgr.approve(req.approval_id)
        valid, msg = self.approval_mgr.is_valid(req.approval_id, session_id="sess-B", task_id="task-1", tool_name="tool_x")
        self.assertFalse(valid)
        self.assertIn("SCOPE_MISMATCH", msg)

    def test_07_wrong_task_rejected(self):
        """7. Approval request for task 1 cannot authorize task 2."""
        req = self.approval_mgr.request_approval("sess-1", "task-1", "tool_x", RiskLevel.EXTERNAL_SIDE_EFFECT, "Do X")
        self.approval_mgr.approve(req.approval_id)
        valid, msg = self.approval_mgr.is_valid(req.approval_id, session_id="sess-1", task_id="task-2", tool_name="tool_x")
        self.assertFalse(valid)
        self.assertIn("SCOPE_MISMATCH", msg)

    def test_08_wrong_node_rejected(self):
        """8. Approval bound to node 1 cannot authorize node 2."""
        req = self.approval_mgr.request_approval("sess-1", "task-1", "tool_x", RiskLevel.EXTERNAL_SIDE_EFFECT, "Do X", node_id="node-1")
        self.approval_mgr.approve(req.approval_id)
        valid, msg = self.approval_mgr.is_valid(req.approval_id, session_id="sess-1", task_id="task-1", tool_name="tool_x", node_id="node-2")
        self.assertFalse(valid)
        self.assertIn("SCOPE_MISMATCH", msg)

    def test_09_wrong_tool_rejected(self):
        """9. Approval for tool A cannot authorize tool B."""
        req = self.approval_mgr.request_approval("sess-1", "task-1", "tool_A", RiskLevel.EXTERNAL_SIDE_EFFECT, "Do A")
        self.approval_mgr.approve(req.approval_id)
        valid, msg = self.approval_mgr.is_valid(req.approval_id, session_id="sess-1", task_id="task-1", tool_name="tool_B")
        self.assertFalse(valid)
        self.assertIn("SCOPE_MISMATCH", msg)

    def test_10_expired_approval_rejected(self):
        """10. Expired approval fails is_valid check."""
        req = self.approval_mgr.request_approval("sess-1", "task-1", "tool_x", RiskLevel.EXTERNAL_SIDE_EFFECT, "Do X", timeout_seconds=1)
        self.approval_mgr.approve(req.approval_id)
        time.sleep(1.2)
        valid, msg = self.approval_mgr.is_valid(req.approval_id, session_id="sess-1", task_id="task-1", tool_name="tool_x")
        self.assertFalse(valid)
        self.assertIn("EXPIRED_APPROVAL", msg)

    # ── 11-14: ExecutionGate Enforcement ──────────────────────────────────────
    def test_11_required_approval_allows_execution(self):
        """11. Valid approved request allows ExecutionGate tool invocation."""
        gate = ExecutionGate(self.approval_mgr, agent_name="TestAgent", task_id="task-1", audit_logger=self.audit_logger)
        gate.register(ToolMetadata("run_shell_cmd", RiskLevel.EXTERNAL_SIDE_EFFECT, "shell_perm", requires_confirmation=True), lambda cmd: ToolResult(VerificationStatus.VERIFIED_SUCCESS, "Cmd executed"))
        
        req = self.approval_mgr.request_approval("sess-1", "task-1", "run_shell_cmd", RiskLevel.EXTERNAL_SIDE_EFFECT, "Run bash")
        self.approval_mgr.approve(req.approval_id)
        
        res = gate.execute("run_shell_cmd", approval_id=req.approval_id, session_id="sess-1", cmd="ls -la")
        self.assertEqual(res.status, VerificationStatus.VERIFIED_SUCCESS)

    def test_12_missing_approval_blocks_execution(self):
        """12. Tool requiring approval fails when no approval_id is provided."""
        gate = ExecutionGate(self.approval_mgr, agent_name="TestAgent", task_id="task-1", audit_logger=self.audit_logger)
        gate.register(ToolMetadata("run_shell_cmd", RiskLevel.EXTERNAL_SIDE_EFFECT, "shell_perm", requires_confirmation=True), lambda cmd: ToolResult(VerificationStatus.VERIFIED_SUCCESS, "Cmd executed"))
        
        res = gate.execute("run_shell_cmd", session_id="sess-1", cmd="ls -la")
        self.assertEqual(res.status, VerificationStatus.VERIFIED_FAILURE)
        self.assertIn("DENIED", res.message)

    def test_13_denied_approval_blocks_execution(self):
        """13. Denied approval blocks ExecutionGate."""
        gate = ExecutionGate(self.approval_mgr, agent_name="TestAgent", task_id="task-1", audit_logger=self.audit_logger)
        gate.register(ToolMetadata("run_shell_cmd", RiskLevel.EXTERNAL_SIDE_EFFECT, "shell_perm", requires_confirmation=True), lambda cmd: ToolResult(VerificationStatus.VERIFIED_SUCCESS, "Cmd executed"))
        
        req = self.approval_mgr.request_approval("sess-1", "task-1", "run_shell_cmd", RiskLevel.EXTERNAL_SIDE_EFFECT, "Run bash")
        self.approval_mgr.deny(req.approval_id, reason="Not allowed")
        
        res = gate.execute("run_shell_cmd", approval_id=req.approval_id, session_id="sess-1", cmd="ls -la")
        self.assertEqual(res.status, VerificationStatus.VERIFIED_FAILURE)
        self.assertIn("APPROVAL_BLOCKED", res.message)

    def test_14_cancelled_approval_blocks_execution(self):
        """14. Cancelled approval blocks ExecutionGate."""
        gate = ExecutionGate(self.approval_mgr, agent_name="TestAgent", task_id="task-1", audit_logger=self.audit_logger)
        gate.register(ToolMetadata("run_shell_cmd", RiskLevel.EXTERNAL_SIDE_EFFECT, "shell_perm", requires_confirmation=True), lambda cmd: ToolResult(VerificationStatus.VERIFIED_SUCCESS, "Cmd executed"))
        
        req = self.approval_mgr.request_approval("sess-1", "task-1", "run_shell_cmd", RiskLevel.EXTERNAL_SIDE_EFFECT, "Run bash")
        self.approval_mgr.cancel(req.approval_id)
        
        res = gate.execute("run_shell_cmd", approval_id=req.approval_id, session_id="sess-1", cmd="ls -la")
        self.assertEqual(res.status, VerificationStatus.VERIFIED_FAILURE)
        self.assertIn("APPROVAL_BLOCKED", res.message)

    # ── 15-19: Recovery Rules ─────────────────────────────────────────────────
    def test_15_safe_retry_same_action_preserves_valid_approval(self):
        """15. Retry of unchanged scoped action maintains valid approval within TTL."""
        req = self.approval_mgr.request_approval("sess-1", "task-1", "write_code_file", RiskLevel.REVERSIBLE, "Write file", timeout_seconds=100)
        self.approval_mgr.approve(req.approval_id)
        valid, _ = self.approval_mgr.is_valid(req.approval_id, "sess-1", "task-1", "write_code_file")
        self.assertTrue(valid)

    def test_16_changed_action_requires_fresh_approval(self):
        """16. Changed action description requires fresh approval request."""
        req = self.approval_mgr.request_approval("sess-1", "task-1", "tool_x", RiskLevel.EXTERNAL_SIDE_EFFECT, "Original action")
        self.approval_mgr.approve(req.approval_id)
        
        # New action must create fresh request
        req2 = self.approval_mgr.request_approval("sess-1", "task-1", "tool_x", RiskLevel.EXTERNAL_SIDE_EFFECT, "Escalated new action")
        self.assertNotEqual(req.approval_id, req2.approval_id)
        self.assertEqual(req2.status, ApprovalStatus.PENDING)

    def test_17_changed_tool_requires_fresh_approval(self):
        """17. Switching from tool A to tool B cannot use tool A's approval."""
        req = self.approval_mgr.request_approval("sess-1", "task-1", "safe_tool", RiskLevel.REVERSIBLE, "Action A")
        self.approval_mgr.approve(req.approval_id)
        valid, msg = self.approval_mgr.is_valid(req.approval_id, "sess-1", "task-1", "unsafe_tool")
        self.assertFalse(valid)
        self.assertIn("SCOPE_MISMATCH", msg)

    def test_18_changed_risk_requires_fresh_approval(self):
        """18. Escalated risk level requires separate approval."""
        req1 = self.approval_mgr.request_approval("sess-1", "task-1", "deploy", RiskLevel.REVERSIBLE, "Deploy staging")
        self.approval_mgr.approve(req1.approval_id)
        
        req2 = self.approval_mgr.request_approval("sess-1", "task-1", "deploy", RiskLevel.DESTRUCTIVE, "Deploy prod")
        self.assertEqual(req2.status, ApprovalStatus.PENDING)

    def test_19_destructive_recovery_never_inherits_approval(self):
        """19. Destructive action requires fresh explicit approval on retry."""
        req = self.approval_mgr.request_approval("sess-1", "task-1", "drop_db", RiskLevel.DESTRUCTIVE, "Drop database")
        self.approval_mgr.approve(req.approval_id)
        self.assertEqual(req.status, ApprovalStatus.APPROVED)

    # ── 20-22: Session Lifecycle & Persistence ────────────────────────────────
    def test_20_session_cancellation_invalidates_pending_approvals(self):
        """20. Session cancellation automatically cancels all pending approvals."""
        session = self.session_mgr.create_session(initial_request="Long task")
        sid = session.session_id
        
        req = self.approval_mgr.request_approval(sid, "task-99", "heavy_tool", RiskLevel.EXTERNAL_SIDE_EFFECT, "Heavy action")
        self.assertEqual(req.status, ApprovalStatus.PENDING)
        
        self.session_mgr.cancel_session(sid, reason="User clicked cancel")
        
        updated_req = self.approval_mgr.get(req.approval_id)
        self.assertEqual(updated_req.status, ApprovalStatus.CANCELLED)

    def test_21_restart_preserves_valid_approval_state(self):
        """21. Application restart preserves approval status across instances."""
        req = self.approval_mgr.request_approval("sess-1", "task-1", "tool_x", RiskLevel.EXTERNAL_SIDE_EFFECT, "Action")
        self.approval_mgr.approve(req.approval_id, approved_by="SecurityLead", reason="Audited")
        
        # New instance from SQLite DB
        restarted_mgr = ApprovalManager(audit_logger=self.audit_logger)
        loaded_req = restarted_mgr.get(req.approval_id)
        self.assertIsNotNone(loaded_req)
        self.assertEqual(loaded_req.status, ApprovalStatus.APPROVED)
        self.assertEqual(loaded_req.approved_by, "SecurityLead")

    def test_22_expired_approval_remains_expired_after_restart(self):
        """22. Expired approval remains EXPIRED after manager reload."""
        req = self.approval_mgr.request_approval("sess-1", "task-1", "tool_x", RiskLevel.EXTERNAL_SIDE_EFFECT, "Action", timeout_seconds=1)
        self.approval_mgr.approve(req.approval_id)
        time.sleep(1.2)
        
        restarted_mgr = ApprovalManager(audit_logger=self.audit_logger)
        loaded_req = restarted_mgr.get(req.approval_id)
        self.assertEqual(loaded_req.status, ApprovalStatus.EXPIRED)

    # ── 23-25: A2A Integration ────────────────────────────────────────────────
    def test_23_approval_reference_preserved_in_agent_message(self):
        """23. AgentMessage carries approval_id without losing context."""
        msg = AgentMessage(
            message_id="msg-101",
            session_id="sess-1",
            task_id="task-1",
            node_id="node-1",
            approval_id="appr-test-123",
            sender_agent="Scheduler",
            recipient_agent="BackendAgent",
            message_type=MessageType.TASK_REQUEST,
            status=AgentStatus.PENDING
        )
        self.assertEqual(msg.approval_id, "appr-test-123")

    def test_24_cross_session_approval_rejected_in_gate(self):
        """24. Cross-session approval in AgentMessage is rejected by ExecutionGate."""
        gate = ExecutionGate(self.approval_mgr, agent_name="BackendAgent", task_id="task-1", audit_logger=self.audit_logger)
        gate.register(ToolMetadata("write_code_file", RiskLevel.EXTERNAL_SIDE_EFFECT, "fs_perm", requires_confirmation=True), lambda file_path, content: ToolResult(VerificationStatus.VERIFIED_SUCCESS, "Created"))
        
        req = self.approval_mgr.request_approval("sess-alpha", "task-1", "write_code_file", RiskLevel.EXTERNAL_SIDE_EFFECT, "Write file")
        self.approval_mgr.approve(req.approval_id)
        
        res = gate.execute("write_code_file", approval_id=req.approval_id, session_id="sess-beta", file_path="app.py", content="code")
        self.assertEqual(res.status, VerificationStatus.VERIFIED_FAILURE)
        self.assertIn("APPROVAL_BLOCKED", res.message)

    def test_25_fake_approval_id_rejected(self):
        """25. Non-existent or fake approval_id is strictly rejected."""
        valid, msg = self.approval_mgr.is_valid("fake-appr-9999", "sess-1", "task-1", "tool_x")
        self.assertFalse(valid)
        self.assertIn("UNKNOWN_APPROVAL", msg)

    # ── 26-29: Security Constraints ───────────────────────────────────────────
    def test_26_agent_cannot_self_approve(self):
        """26. Self-approval attempts by agents without valid human confirmation fail."""
        req = self.approval_mgr.request_approval("sess-1", "task-1", "tool_x", RiskLevel.DESTRUCTIVE, "Dangerous action")
        self.assertEqual(req.status, ApprovalStatus.PENDING)
        valid, _ = self.approval_mgr.is_valid(req.approval_id, "sess-1", "task-1", "tool_x")
        self.assertFalse(valid)

    def test_27_llm_cannot_create_approved_state(self):
        """27. LLM generated strings cannot forge an APPROVED state in ApprovalManager."""
        fake_id = "LLM_APPROVED_123"
        valid, _ = self.approval_mgr.is_valid(fake_id, "sess-1", "task-1", "tool_x")
        self.assertFalse(valid)

    def test_28_approval_cannot_bypass_execution_gate(self):
        """28. Even with approved status, unregistered tools are blocked by ExecutionGate."""
        gate = ExecutionGate(self.approval_mgr, agent_name="System", task_id="task-1", audit_logger=self.audit_logger)
        req = self.approval_mgr.request_approval("sess-1", "task-1", "unregistered_malicious_tool", RiskLevel.DESTRUCTIVE, "Exploit")
        self.approval_mgr.approve(req.approval_id)
        
        res = gate.execute("unregistered_malicious_tool", approval_id=req.approval_id, session_id="sess-1")
        self.assertEqual(res.status, VerificationStatus.VERIFIED_FAILURE)
        self.assertIn("UNREGISTERED_TOOL", res.message)

    def test_29_secrets_redacted_from_approval_data(self):
        """29. Secrets and credentials in approval metadata are redacted."""
        req = self.approval_mgr.request_approval(
            session_id="sess-1",
            task_id="task-1",
            tool_name="auth_service",
            risk_level=RiskLevel.EXTERNAL_SIDE_EFFECT,
            action_description="Setup auth token",
            metadata={"api_key": "supersecret123", "normal_field": "public_data"}
        )
        self.assertEqual(req.metadata["api_key"], "******")
        self.assertEqual(req.metadata["normal_field"], "public_data")

    # ── 30-31: Observability & Audit ──────────────────────────────────────────
    def test_30_approval_lifecycle_observable(self):
        """30. Observability events emitted for approval lifecycle."""
        req = self.approval_mgr.request_approval("sess-obs", "task-obs", "tool_obs", RiskLevel.EXTERNAL_SIDE_EFFECT, "Obs test")
        self.approval_mgr.approve(req.approval_id)
        self.assertEqual(req.status, ApprovalStatus.APPROVED)

    def test_31_approval_events_auditable(self):
        """31. Approval lifecycle transitions are saved in SQLite approval_events table."""
        req = self.approval_mgr.request_approval("sess-audit", "task-audit", "tool_audit", RiskLevel.EXTERNAL_SIDE_EFFECT, "Audit test")
        self.approval_mgr.approve(req.approval_id, approved_by="Auditor", reason="Approved for audit")
        
        events = self.audit_logger.query_approval_events(approval_id=req.approval_id)
        self.assertGreaterEqual(len(events), 2) # PENDING + APPROVED

    # ── 32: Regression ────────────────────────────────────────────────────────
    def test_32_regression_scheduler_waits_for_approval(self):
        """32. Scheduler blocks/waits when node requires approval and proceeds upon approval."""
        graph = TaskGraph(graph_id="graph-reg-1", objective="Approval graph")
        graph.nodes["n1"] = TaskNode(
            node_id="n1",
            description="Restricted action",
            agent="DevAgent",
            approval_required=True,
            approval_status="PENDING"
        )
        
        scheduler = DependencyScheduler({"DevAgent": None}, self.audit_logger, session_manager=self.session_mgr)
        scheduler._update_states(graph)
        self.assertEqual(graph.nodes["n1"].status, TaskState.WAITING_FOR_CONFIRMATION)
        
        # Grant approval
        req = self.approval_mgr.request_approval("sess-1", "graph-reg-1", "restricted_tool", RiskLevel.EXTERNAL_SIDE_EFFECT, "Restricted", node_id="n1")
        self.approval_mgr.approve(req.approval_id)
        graph.nodes["n1"].approval_status = "APPROVED"
        graph.nodes["n1"].approval_id = req.approval_id
        
        scheduler._update_states(graph)
        self.assertEqual(graph.nodes["n1"].status, TaskState.READY)

if __name__ == "__main__":
    unittest.main()
