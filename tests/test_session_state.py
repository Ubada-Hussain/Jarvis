import unittest
import os
import tempfile
import time
from unittest.mock import MagicMock

from core.session_state import SessionManager, SessionState, SessionStatus, sanitize_session_data
from core.audit_logger import SQLiteAuditLogger
from core.observability import observability_manager, ObservabilityEvent
from core.planner import TaskPlanner, TaskGraph, TaskNode, TaskState
from core.scheduler import DependencyScheduler
from core.a2a import AgentMessage, MessageType, AgentStatus
from core.verification import ToolResult, VerificationStatus
from core.tool_registry import tool_registry

class TestSessionState(unittest.TestCase):
    def setUp(self):
        self.db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.db_file.name
        self.db_file.close()
        self.audit_logger = SQLiteAuditLogger(self.db_path)
        self.session_mgr = SessionManager(audit_logger=self.audit_logger)

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception:
                pass

    # ── 1. Session Creation ───────────────────────────────────────────────────
    def test_01_session_creation(self):
        """1. Session creation generates unique session_id and NEW status."""
        session = self.session_mgr.create_session(initial_request="Build an API")
        self.assertTrue(session.session_id.startswith("sess-"))
        self.assertEqual(session.session_status, SessionStatus.NEW)
        self.assertEqual(session.current_request, "Build an API")

    # ── 2. Session State Transitions ──────────────────────────────────────────
    def test_02_session_state_transitions(self):
        """2. Valid session state transitions work sequentially."""
        session = self.session_mgr.create_session(initial_request="Run tests")
        sid = session.session_id
        
        # NEW -> PLANNING
        self.session_mgr.transition_state(sid, SessionStatus.PLANNING, reason="Starting planner")
        self.assertEqual(self.session_mgr.get_session(sid).session_status, SessionStatus.PLANNING)
        
        # PLANNING -> EXECUTING
        self.session_mgr.transition_state(sid, SessionStatus.EXECUTING, reason="Executing graph")
        self.assertEqual(self.session_mgr.get_session(sid).session_status, SessionStatus.EXECUTING)
        
        # EXECUTING -> COMPLETED
        self.session_mgr.transition_state(sid, SessionStatus.COMPLETED, reason="All tasks passed")
        self.assertEqual(self.session_mgr.get_session(sid).session_status, SessionStatus.COMPLETED)

    # ── 3. Invalid State Transition Rejection ─────────────────────────────────
    def test_03_invalid_state_transition_rejection(self):
        """3. Illegal state transitions raise ValueError."""
        session = self.session_mgr.create_session(initial_request="Invalid transition")
        sid = session.session_id
        
        # NEW -> COMPLETED directly is invalid
        with self.assertRaises(ValueError):
            self.session_mgr.transition_state(sid, SessionStatus.COMPLETED)

    # ── 4. Session Isolation ──────────────────────────────────────────────────
    def test_04_session_isolation(self):
        """4. Session A and Session B maintain strictly isolated state."""
        sess_a = self.session_mgr.create_session(initial_request="Task A")
        sess_b = self.session_mgr.create_session(initial_request="Task B")
        
        self.session_mgr.update_session(sess_a.session_id, active_agent="BackendAgent")
        self.session_mgr.update_session(sess_b.session_id, active_agent="FrontendAgent")
        
        self.assertEqual(self.session_mgr.get_session(sess_a.session_id).active_agent, "BackendAgent")
        self.assertEqual(self.session_mgr.get_session(sess_b.session_id).active_agent, "FrontendAgent")

    # ── 5. TaskGraph Association ──────────────────────────────────────────────
    def test_05_task_graph_association(self):
        """5. TaskGraph ID is recorded on SessionState during scheduling."""
        session = self.session_mgr.create_session(initial_request="Run graph")
        sid = session.session_id
        
        graph = TaskGraph(graph_id="graph-123", objective="Run graph")
        graph.nodes["n1"] = TaskNode(node_id="n1", description="node", agent="DevAgent")
        
        mock_agent = MagicMock()
        mock_agent.execute.return_value = "Done"
        scheduler = DependencyScheduler({"DevAgent": mock_agent}, self.audit_logger)
        
        scheduler.execute_graph(graph, session_id=sid)
        updated_sess = self.session_mgr.get_session(sid)
        self.assertEqual(updated_sess.active_task_graph_id, "graph-123")

    # ── 6. A2A Correlation ────────────────────────────────────────────────────
    def test_06_a2a_correlation(self):
        """6. AgentMessage correlates session_id, task_id, node_id."""
        msg = AgentMessage(
            message_id="msg-1",
            session_id="sess-xyz",
            task_id="graph-xyz",
            node_id="n1",
            sender_agent="Scheduler",
            recipient_agent="BackendAgent",
            message_type=MessageType.TASK_REQUEST,
            status=AgentStatus.PENDING
        )
        self.assertEqual(msg.session_id, "sess-xyz")
        self.assertEqual(msg.node_id, "n1")

    # ── 7. Clarification Pause / Resume ───────────────────────────────────────
    def test_07_clarification_pause_resume(self):
        """7. Ambiguous intent transitions to WAITING_FOR_CLARIFICATION and resumes."""
        session = self.session_mgr.create_session(initial_request="Fix it")
        sid = session.session_id
        
        self.session_mgr.transition_state(sid, SessionStatus.WAITING_FOR_CLARIFICATION, reason="Ambiguous request")
        self.assertEqual(self.session_mgr.get_session(sid).session_status, SessionStatus.WAITING_FOR_CLARIFICATION)
        
        # User provides clarification -> Resumes to PLANNING
        self.session_mgr.update_session(sid, pending_clarification=False, current_request="Fix database connection in config.py")
        self.session_mgr.transition_state(sid, SessionStatus.PLANNING, reason="Clarification received")
        self.assertEqual(self.session_mgr.get_session(sid).session_status, SessionStatus.PLANNING)

    # ── 8. Cancellation ───────────────────────────────────────────────────────
    def test_08_cancellation(self):
        """8. Cancellation transitions state to CANCELLED and is never reported as success."""
        session = self.session_mgr.create_session(initial_request="Cancel task")
        sid = session.session_id
        
        self.session_mgr.transition_state(sid, SessionStatus.PLANNING)
        self.session_mgr.cancel_session(sid, reason="User clicked stop")
        
        updated = self.session_mgr.get_session(sid)
        self.assertEqual(updated.session_status, SessionStatus.CANCELLED)
        self.assertNotEqual(updated.session_status, SessionStatus.COMPLETED)

    # ── 9. Recovery State ─────────────────────────────────────────────────────
    def test_09_recovery_state(self):
        """9. Session transitions to RECOVERING during retry attempt."""
        session = self.session_mgr.create_session(initial_request="Recover task")
        sid = session.session_id
        
        self.session_mgr.transition_state(sid, SessionStatus.PLANNING)
        self.session_mgr.transition_state(sid, SessionStatus.EXECUTING)
        self.session_mgr.transition_state(sid, SessionStatus.RECOVERING, reason="Retrying failed node")
        
        self.assertEqual(self.session_mgr.get_session(sid).session_status, SessionStatus.RECOVERING)

    # ── 10. Verified Result Recording ─────────────────────────────────────────
    def test_10_verified_result_recording(self):
        """10. Verified results are safely recorded into recent_verified_results."""
        session = self.session_mgr.create_session(initial_request="Verify task")
        sid = session.session_id
        
        self.session_mgr.add_verified_result(sid, "node-1", "BackendAgent", "API built", "file on disk")
        updated = self.session_mgr.get_session(sid)
        self.assertEqual(len(updated.recent_verified_results), 1)
        self.assertEqual(updated.recent_verified_results[0]["result"], "API built")

    # ── 11. Unverified Result Rejection ───────────────────────────────────────
    def test_11_unverified_result_rejection(self):
        """11. Only explicit verified calls populate verified results list."""
        session = self.session_mgr.create_session(initial_request="Unverified test")
        sid = session.session_id
        
        # Failure is added to failures list, not verified results
        self.session_mgr.add_failure(sid, "node-1", "BackendAgent", "Timeout", "TIMEOUT")
        updated = self.session_mgr.get_session(sid)
        self.assertEqual(len(updated.recent_verified_results), 0)
        self.assertEqual(len(updated.recent_failures), 1)

    # ── 12. Persistence / Reload ──────────────────────────────────────────────
    def test_12_persistence_reload(self):
        """12. SessionState is persisted to SQLite and reloaded faithfully."""
        session = self.session_mgr.create_session(conversation_id="conv-1", initial_request="Persist test")
        sid = session.session_id
        self.session_mgr.update_session(sid, active_agent="AcademicAgent")
        
        # New manager instance reading the same DB
        new_mgr = SessionManager(audit_logger=self.audit_logger)
        loaded = new_mgr.get_session(sid)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.conversation_id, "conv-1")
        self.assertEqual(loaded.active_agent, "AcademicAgent")

    # ── 13. Secret Redaction ──────────────────────────────────────────────────
    def test_13_secret_redaction(self):
        """13. API keys and passwords are redacted from session data."""
        clean = sanitize_session_data({"password": "supersecret123", "normal_key": "safe_value"})
        self.assertEqual(clean["password"], "******")
        self.assertEqual(clean["normal_key"], "safe_value")

    # ── 14. Observability ─────────────────────────────────────────────────────
    def test_14_observability(self):
        """14. Observability events emitted during session lifecycle."""
        captured = []
        def handler(e):
            captured.append(e)
        observability_manager.register_callback(handler)
        
        session = self.session_mgr.create_session(initial_request="Obs test")
        self.session_mgr.transition_state(session.session_id, SessionStatus.PLANNING)
        self.session_mgr.transition_state(session.session_id, SessionStatus.CANCELLED)
        
        ev_types = [e.get("event", {}).get("event_type") for e in captured if isinstance(e, dict)]
        self.assertIn("SESSION_CREATED", ev_types)
        self.assertIn("SESSION_CANCELLED", ev_types)

    # ── 15. Audit ─────────────────────────────────────────────────────────────
    def test_15_audit(self):
        """15. Session transitions are recorded in SQLite session_events table."""
        session = self.session_mgr.create_session(initial_request="Audit test")
        sid = session.session_id
        self.session_mgr.transition_state(sid, SessionStatus.PLANNING, reason="Planner started")
        
        events = self.audit_logger.query_session_events(session_id=sid)
        self.assertTrue(len(events) >= 2)
        states = [e["new_state"] for e in events]
        self.assertIn("NEW", states)
        self.assertIn("PLANNING", states)

    # ── 16. Cross-Session Contamination Prevention ────────────────────────────
    def test_16_cross_session_contamination_prevention(self):
        """16. Failures in Session A do not leak into Session B."""
        sess_a = self.session_mgr.create_session(initial_request="Session A")
        sess_b = self.session_mgr.create_session(initial_request="Session B")
        
        self.session_mgr.add_failure(sess_a.session_id, "n1", "DevAgent", "Error in A")
        
        self.assertEqual(len(self.session_mgr.get_session(sess_a.session_id).recent_failures), 1)
        self.assertEqual(len(self.session_mgr.get_session(sess_b.session_id).recent_failures), 0)

    # ── 17. Application Restart Recovery ──────────────────────────────────────
    def test_17_app_restart_recovery(self):
        """17. Reloading active session after crash retains exact status without false success."""
        session = self.session_mgr.create_session(initial_request="Crash test")
        sid = session.session_id
        self.session_mgr.transition_state(sid, SessionStatus.PLANNING)
        self.session_mgr.transition_state(sid, SessionStatus.EXECUTING)
        
        # Simulate restart with fresh manager
        restarted_mgr = SessionManager(audit_logger=self.audit_logger)
        reloaded = restarted_mgr.get_session(sid)
        self.assertEqual(reloaded.session_status, SessionStatus.EXECUTING)
        self.assertNotEqual(reloaded.session_status, SessionStatus.COMPLETED)

    # ── 18. Tasks 1–12 Regression ─────────────────────────────────────────────
    def test_18_tasks_1_to_12_regression(self):
        """18. Tool registry and core capabilities remain fully operational."""
        self.assertIsNotNone(tool_registry.get("read_code_file"))
        self.assertIsNotNone(tool_registry.get("write_code_file"))
        self.assertIsNotNone(tool_registry.get("run_backend_tests"))

if __name__ == "__main__":
    unittest.main()
