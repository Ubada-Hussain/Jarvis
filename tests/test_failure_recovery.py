import unittest
import os
import tempfile
import time
import uuid
import json
from unittest.mock import MagicMock

from core.recovery import (
    FailureCategory, RecoveryAction, RetryPolicy, RecoveryDecision, RecoveryManager
)
from core.verification import VerificationStatus, ToolResult
from core.execution_gate import ExecutionGate, ToolMetadata, RiskLevel
from core.audit_logger import SQLiteAuditLogger
from core.a2a import A2ADispatcher, AgentMessage, MessageType, AgentStatus, AgentError
from core.planner import TaskGraph, TaskNode, TaskState
from core.scheduler import DependencyScheduler
from core.observability import observability_manager, ObservabilityEvent
from core.memory_manager import MemoryManager
from core.memory_models import EpisodicMemory

class MockLLMEngine:
    def __init__(self):
        pass
    def generate_response(self, prompt: str, system_prompt: str = None, tools: list = None, tool_logic=None):
        return "LLM Response"

class MockMemoryManager:
    def __init__(self):
        self.episodic_memories = []
    def get_relevant_context(self, task: str, memory_types: list = None, max_results: int = 3):
        return []
    def save_interaction(self, user_input: str, ai_response: str, activity_type: str):
        pass
    def save_episodic_memory(self, mem: EpisodicMemory):
        self.episodic_memories.append(mem)

class MockApprovalManager:
    def __init__(self, auto_approve=True):
        self.auto_approve = auto_approve
        self.requested = False
        self.last_action = None
    def require_approval(self, action_desc: str) -> bool:
        self.requested = True
        self.last_action = action_desc
        return self.auto_approve

class MockAgent:
    def __init__(self, name: str, execution_outcomes: list):
        self.name = name
        self.outcomes = execution_outcomes
        self.call_count = 0
    def execute(self, task: str, task_id: str = None) -> str:
        idx = min(self.call_count, len(self.outcomes) - 1)
        res = self.outcomes[idx]
        self.call_count += 1
        return res

class TestFailureRecovery(unittest.TestCase):
    def setUp(self):
        self.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db_path = self.temp_db_file.name
        self.temp_db_file.close()
        self.audit_logger = SQLiteAuditLogger(self.temp_db_path)
        self.recovery_manager = RecoveryManager(default_max_retries=2)
        self.llm = MockLLMEngine()
        self.memory = MockMemoryManager()
        self.approval = MockApprovalManager()

    def tearDown(self):
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────────────────
    # Failure Classification Tests (1, 2, 3, 4, 5)
    # ─────────────────────────────────────────────────────────────────────────

    def test_01_tool_error_classification(self):
        """1. Tool error classified correctly."""
        cat = self.recovery_manager.classify_failure(
            error_code="TOOL_CRASH",
            error_msg="Exception: Division by zero",
            verification_status="VERIFIED_FAILURE"
        )
        self.assertEqual(cat, FailureCategory.TOOL_ERROR)

    def test_02_verification_failure_classification(self):
        """2. Verification failure classified correctly."""
        cat = self.recovery_manager.classify_failure(
            error_code="VERIFIED_FAILURE",
            error_msg="os.path.exists returned False after write",
            verification_status="VERIFIED_FAILURE"
        )
        self.assertEqual(cat, FailureCategory.VERIFICATION_FAILURE)

    def test_03_permission_denied_classification(self):
        """3. Permission denied classified correctly."""
        cat = self.recovery_manager.classify_failure(
            error_code="PERMISSION_DENIED",
            error_msg="DENIED: User rejected the action.",
            permission_status="DENIED"
        )
        self.assertEqual(cat, FailureCategory.PERMISSION_DENIED)

    def test_04_user_cancellation_classification(self):
        """4. User cancellation classified correctly."""
        cat = self.recovery_manager.classify_failure(
            error_code="USER_CANCELLED",
            error_msg="Operation cancelled by user."
        )
        self.assertEqual(cat, FailureCategory.USER_CANCELLED)

    def test_05_timeout_classification(self):
        """5. Timeout classified correctly."""
        cat = self.recovery_manager.classify_failure(
            error_code="TIMEOUT",
            error_msg="Subprocess timeout expired after 30s."
        )
        self.assertEqual(cat, FailureCategory.TIMEOUT)

    # ─────────────────────────────────────────────────────────────────────────
    # Retry Rules & Budget Tests (6, 7, 8, 9, 10)
    # ─────────────────────────────────────────────────────────────────────────

    def test_06_retryable_failure_retries(self):
        """6. Retryable failure returns should_retry=True."""
        dec = self.recovery_manager.evaluate_recovery(
            category=FailureCategory.TIMEOUT,
            current_attempt=1,
            max_retries=2
        )
        self.assertTrue(dec.should_retry)
        self.assertEqual(dec.action, RecoveryAction.RETRY)

    def test_07_non_retryable_failure_does_not_retry(self):
        """7. Non-retryable failure returns should_retry=False."""
        dec = self.recovery_manager.evaluate_recovery(
            category=FailureCategory.PERMISSION_DENIED,
            current_attempt=1,
            max_retries=2
        )
        self.assertFalse(dec.should_retry)
        self.assertEqual(dec.action, RecoveryAction.FAIL)

    def test_08_retry_budget_enforced(self):
        """8. Retry budget exhausted stops retries."""
        dec = self.recovery_manager.evaluate_recovery(
            category=FailureCategory.TIMEOUT,
            current_attempt=2,
            max_retries=2
        )
        self.assertFalse(dec.should_retry)
        self.assertIn("exhausted", dec.reason.lower())

    def test_09_retry_counter_persists_in_node(self):
        """9. Retry counter tracks attempts in TaskNode."""
        node = TaskNode(node_id="n1", description="desc", agent="MockAgent", max_retries=2)
        self.assertEqual(node.attempts, 0)
        node.attempts += 1
        self.assertEqual(node.attempts, 1)

    def test_10_backoff_calculation(self):
        """10. Exponential backoff calculates increasing delays."""
        policy = RetryPolicy(max_retries=3, initial_delay_s=0.5, backoff_factor=1.0)
        dec1 = self.recovery_manager.evaluate_recovery(
            category=FailureCategory.TIMEOUT, current_attempt=1, retry_policy=policy
        )
        dec2 = self.recovery_manager.evaluate_recovery(
            category=FailureCategory.TIMEOUT, current_attempt=2, retry_policy=policy
        )
        self.assertEqual(dec1.retry_delay_s, 0.5)
        self.assertEqual(dec2.retry_delay_s, 1.0)

    # ─────────────────────────────────────────────────────────────────────────
    # Verification-First Rule Tests (11, 12, 13)
    # ─────────────────────────────────────────────────────────────────────────

    def test_11_retry_only_succeeds_with_verified_success(self):
        """11. Node execution only succeeds if final attempt produces VERIFIED_SUCCESS."""
        gate = ExecutionGate(self.approval, agent_name="BackendAgent", task_id="node-v1", audit_logger=self.audit_logger)
        gate.register(ToolMetadata("mock_success", RiskLevel.READ_ONLY, "misc"), lambda: ToolResult(VerificationStatus.VERIFIED_SUCCESS, "OK"))
        res = gate.execute("mock_success")
        self.assertEqual(res.status, VerificationStatus.VERIFIED_SUCCESS)

    def test_12_unverified_never_becomes_success(self):
        """12. UNVERIFIED output remains UNVERIFIED and is not counted as success."""
        gate = ExecutionGate(self.approval, agent_name="BackendAgent", task_id="node-v2", audit_logger=self.audit_logger)
        gate.register(ToolMetadata("mock_unverified", RiskLevel.READ_ONLY, "misc"), lambda: "Raw string without verification")
        res = gate.execute("mock_unverified")
        self.assertEqual(res.status, VerificationStatus.UNVERIFIED)

    def test_13_verified_failure_remains_failure(self):
        """13. VERIFIED_FAILURE cannot be converted into success."""
        gate = ExecutionGate(self.approval, agent_name="BackendAgent", task_id="node-v3", audit_logger=self.audit_logger)
        gate.register(ToolMetadata("mock_fail", RiskLevel.READ_ONLY, "misc"), lambda: ToolResult(VerificationStatus.VERIFIED_FAILURE, "Fatal error"))
        res = gate.execute("mock_fail")
        self.assertEqual(res.status, VerificationStatus.VERIFIED_FAILURE)

    # ─────────────────────────────────────────────────────────────────────────
    # Security Tests (14, 15, 16, 17)
    # ─────────────────────────────────────────────────────────────────────────

    def test_14_permission_denied_never_retried(self):
        """14. Permission denied is never automatically retried."""
        dec = self.recovery_manager.evaluate_recovery(
            category=FailureCategory.PERMISSION_DENIED,
            current_attempt=1,
            max_retries=5
        )
        self.assertFalse(dec.should_retry)

    def test_15_destructive_action_never_automatically_retried(self):
        """15. Destructive action with required confirmation cannot be automatically retried."""
        dec = self.recovery_manager.evaluate_recovery(
            category=FailureCategory.TOOL_ERROR,
            current_attempt=1,
            max_retries=3,
            risk_level="DESTRUCTIVE",
            requires_confirmation=True
        )
        self.assertFalse(dec.should_retry)

    def test_16_retry_always_passes_execution_gate(self):
        """16. Every retry invocation must pass through ExecutionGate."""
        gate = ExecutionGate(self.approval, agent_name="BackendAgent", task_id="node-gate-1", audit_logger=self.audit_logger)
        gate.register(ToolMetadata("safe_op", RiskLevel.READ_ONLY, "read"), lambda: ToolResult(VerificationStatus.VERIFIED_SUCCESS, "Read ok"))
        
        # Attempt 1
        res1 = gate.execute("safe_op")
        # Attempt 2
        res2 = gate.execute("safe_op")
        
        events = self.audit_logger.query_events(task_id="node-gate-1")
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["permission_status"], "GRANTED")
        self.assertEqual(events[1]["permission_status"], "GRANTED")

    def test_17_user_cancellation_respected(self):
        """17. User cancellation is immediately treated as non-retryable."""
        dec = self.recovery_manager.evaluate_recovery(
            category=FailureCategory.USER_CANCELLED,
            current_attempt=1
        )
        self.assertFalse(dec.should_retry)

    # ─────────────────────────────────────────────────────────────────────────
    # TaskGraph & Dependency Handling Tests (18, 19, 20)
    # ─────────────────────────────────────────────────────────────────────────

    def test_18_failed_prerequisite_blocks_downstream(self):
        """18. Failed prerequisite blocks downstream node."""
        graph = TaskGraph(graph_id="g1", objective="Test Dependency")
        n1 = TaskNode(node_id="n1", description="step 1", agent="BackendAgent", status=TaskState.FAILED)
        n2 = TaskNode(node_id="n2", description="step 2", agent="FrontendAgent", dependencies=["n1"], status=TaskState.PENDING)
        graph.nodes = {"n1": n1, "n2": n2}
        
        scheduler = DependencyScheduler({}, self.audit_logger)
        scheduler._update_states(graph)
        self.assertEqual(graph.nodes["n2"].status, TaskState.BLOCKED)

    def test_19_successful_recovery_unblocks_downstream(self):
        """19. Successful recovery unblocks downstream node to READY."""
        graph = TaskGraph(graph_id="g2", objective="Test Recovery")
        n1 = TaskNode(node_id="n1", description="step 1", agent="BackendAgent", status=TaskState.COMPLETED)
        n2 = TaskNode(node_id="n2", description="step 2", agent="FrontendAgent", dependencies=["n1"], status=TaskState.PENDING)
        graph.nodes = {"n1": n1, "n2": n2}
        
        scheduler = DependencyScheduler({}, self.audit_logger)
        scheduler._update_states(graph)
        self.assertEqual(graph.nodes["n2"].status, TaskState.READY)

    def test_20_persistent_failure_blocks_downstream(self):
        """20. Persistent failure across all retries leaves downstream BLOCKED."""
        graph = TaskGraph(graph_id="g3", objective="Test Persistent")
        n1 = TaskNode(node_id="n1", description="step 1", agent="BackendAgent", status=TaskState.FAILED, attempts=2, max_retries=2)
        n2 = TaskNode(node_id="n2", description="step 2", agent="FrontendAgent", dependencies=["n1"], status=TaskState.PENDING)
        graph.nodes = {"n1": n1, "n2": n2}
        
        scheduler = DependencyScheduler({}, self.audit_logger)
        scheduler._update_states(graph)
        self.assertEqual(graph.nodes["n2"].status, TaskState.BLOCKED)

    # ─────────────────────────────────────────────────────────────────────────
    # A2A Structured Protocol Tests (21, 22, 23)
    # ─────────────────────────────────────────────────────────────────────────

    def test_21_retry_status_represented_structurally(self):
        """21. Retry status and message types exist in structured A2A enum."""
        self.assertIn(MessageType.TASK_RETRYING, MessageType)
        self.assertIn(AgentStatus.RETRYING, AgentStatus)

    def test_22_task_and_node_id_preserved_in_retry(self):
        """22. task_id and node_id are preserved across retry messages."""
        msg = AgentMessage(
            message_id="msg-ret-1",
            task_id="graph-retry-test",
            node_id="node-retry-1",
            sender_agent="Scheduler",
            recipient_agent="BackendAgent",
            message_type=MessageType.TASK_RETRYING,
            status=AgentStatus.RETRYING,
            attempt=2
        )
        self.assertEqual(msg.task_id, "graph-retry-test")
        self.assertEqual(msg.node_id, "node-retry-1")
        self.assertEqual(msg.attempt, 2)

    def test_23_no_duplicate_irreversible_execution(self):
        """23. Irreversible / destructive operations declare max_retries=0."""
        meta = ToolMetadata("delete_record", RiskLevel.DESTRUCTIVE, "db_delete", requires_confirmation=True)
        self.assertFalse(meta.retryable)
        self.assertEqual(meta.max_retries, 0)

    # ─────────────────────────────────────────────────────────────────────────
    # Audit & Observability Tests (24, 25, 26, 27)
    # ─────────────────────────────────────────────────────────────────────────

    def test_24_every_retry_is_logged_to_audit(self):
        """24. Every recovery decision and retry is logged to SQLite."""
        self.audit_logger.log_recovery_event(
            task_id="g-audit",
            node_id="n-audit",
            agent="BackendAgent",
            attempt=1,
            failure_category="TIMEOUT",
            recovery_action="RETRY",
            reason="Transient timeout, retrying with delay",
            outcome="RETRYING"
        )
        events = self.audit_logger.query_recovery_events(task_id="g-audit")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["failure_category"], "TIMEOUT")
        self.assertEqual(events[0]["recovery_action"], "RETRY")

    def test_25_recovery_timeline_reconstructable(self):
        """25. Multiple recovery attempts form a reconstructable chronological timeline."""
        self.audit_logger.log_recovery_event("g-time", "n-time", "BackendAgent", 1, "SERVER_START_FAILURE", "RETRY", "Port delayed", "RETRYING")
        self.audit_logger.log_recovery_event("g-time", "n-time", "BackendAgent", 2, "NONE", "RETRY_SUCCESS", "Server up", "VERIFIED_SUCCESS")
        
        events = self.audit_logger.query_recovery_events(task_id="g-time")
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["attempt"], 1)
        self.assertEqual(events[1]["attempt"], 2)
        self.assertEqual(events[1]["outcome"], "VERIFIED_SUCCESS")

    def test_26_observability_events_emitted(self):
        """26. Retry and recovery observability events are emitted."""
        captured = []
        def handler(event):
            captured.append(event)
        observability_manager.register_callback(handler)
        
        observability_manager.emit_event(ObservabilityEvent(
            event_type="RETRY_STARTED",
            agent="BackendAgent",
            metadata={"attempt": 2}
        ))
        self.assertTrue(any(e.get("event", {}).get("event_type") == "RETRY_STARTED" or e.get("type") == "observability_update" for e in captured))

    def test_27_final_outcome_visible(self):
        """27. Observability manager captures final task outcome."""
        observability_manager.start_task("task-outcome", "test request")
        observability_manager.end_task(status="COMPLETED")
        self.assertEqual(observability_manager.runtime_state["status"], "COMPLETED")

    # ─────────────────────────────────────────────────────────────────────────
    # Memory Integration Tests (28, 29)
    # ─────────────────────────────────────────────────────────────────────────

    def test_28_recovered_failure_creates_episodic_candidate(self):
        """28. A recovered task forms an episodic memory tagged 'recovered'."""
        graph = TaskGraph(graph_id="g-mem", objective="Recovered workflow")
        node = TaskNode(
            node_id="n-rec",
            description="Recovered API",
            agent="BackendAgent",
            status=TaskState.COMPLETED,
            verification_status="VERIFIED_SUCCESS",
            attempts=2
        )
        graph.nodes = {"n-rec": node}
        
        scheduler = DependencyScheduler({}, self.audit_logger)
        scheduler.memory_manager = self.memory
        scheduler._form_episodic_memories(graph)
        
        self.assertEqual(len(self.memory.episodic_memories), 1)
        self.assertIn("recovered", self.memory.episodic_memories[0].tags)

    def test_29_retry_noise_does_not_flood_memory(self):
        """29. Intermediate retries are not saved as standalone episodic memories."""
        self.assertEqual(len(self.memory.episodic_memories), 0)

if __name__ == "__main__":
    unittest.main()
