import unittest
import uuid
import json
from core.a2a import AgentMessage, MessageType, AgentStatus, A2ADispatcher, AgentError

class MockAgent:
    def __init__(self, name):
        self.name = name
        self.called = False
    def execute(self, task: str, task_id: str = None) -> str:
        self.called = True
        return f"Mock result for {task}"

class MockAuditLogger:
    def __init__(self, events):
        self.events = events
        self.a2a_log = []
    def query_events(self, task_id=None, **kwargs):
        return [e for e in self.events if e.get("task_id") == task_id]
    def log_a2a_message(self, message):
        self.a2a_log.append(message)

class TestA2A(unittest.TestCase):
    def test_message_validation(self):
        # Valid message
        msg = AgentMessage(
            message_id="123",
            sender_agent="A",
            recipient_agent="B",
            message_type=MessageType.TASK_REQUEST,
            status=AgentStatus.PENDING
        )
        self.assertEqual(msg.sender_agent, "A")
        
        # Missing required field
        with self.assertRaises(ValueError):
            AgentMessage(sender_agent="A", recipient_agent="B")

    def test_dispatcher_success(self):
        agents = {"TargetAgent": MockAgent("TargetAgent")}
        audit_events = [
            {"task_id": "n1", "tool": "test_tool", "evidence": "Did the thing", "verification_status": "VERIFIED_SUCCESS"}
        ]
        logger = MockAuditLogger(audit_events)
        dispatcher = A2ADispatcher(agents, logger)
        
        req = AgentMessage(
            message_id="m1",
            task_id="t1",
            node_id="n1",
            sender_agent="Scheduler",
            recipient_agent="TargetAgent",
            message_type=MessageType.TASK_REQUEST,
            status=AgentStatus.PENDING,
            result="Do this"
        )
        
        resp = dispatcher.dispatch(req)
        
        self.assertEqual(resp.message_type, MessageType.TASK_RESULT)
        self.assertEqual(resp.status, AgentStatus.COMPLETED)
        self.assertEqual(resp.sender_agent, "TargetAgent")
        self.assertEqual(resp.recipient_agent, "Scheduler")
        self.assertTrue(agents["TargetAgent"].called)
        self.assertEqual(len(resp.evidence), 1)
        self.assertIn("Did the thing", resp.evidence[0])

    def test_dispatcher_failure(self):
        agents = {"TargetAgent": MockAgent("TargetAgent")}
        # Simulate tool verification failure
        audit_events = [
            {"task_id": "n2", "tool": "bad_tool", "error": "Crash", "verification_status": "VERIFIED_FAILURE"}
        ]
        logger = MockAuditLogger(audit_events)
        dispatcher = A2ADispatcher(agents, logger)
        
        req = AgentMessage(
            message_id="m2",
            task_id="t2",
            node_id="n2",
            sender_agent="Scheduler",
            recipient_agent="TargetAgent",
            message_type=MessageType.TASK_REQUEST,
            status=AgentStatus.PENDING,
            result="Fail this"
        )
        
        resp = dispatcher.dispatch(req)
        
        self.assertEqual(resp.message_type, MessageType.TASK_FAILED)
        self.assertEqual(resp.status, AgentStatus.FAILED)
        self.assertEqual(len(resp.errors), 1)
        self.assertEqual(resp.errors[0].code, "VERIFIED_FAILURE")

    def test_dispatcher_permission_denied(self):
        agents = {"TargetAgent": MockAgent("TargetAgent")}
        audit_events = [
            {"task_id": "n3", "tool": "secret_tool", "permission_status": "DENIED"}
        ]
        logger = MockAuditLogger(audit_events)
        dispatcher = A2ADispatcher(agents, logger)
        
        req = AgentMessage(
            message_id="m3",
            task_id="t3",
            node_id="n3",
            sender_agent="Scheduler",
            recipient_agent="TargetAgent",
            message_type=MessageType.TASK_REQUEST,
            status=AgentStatus.PENDING,
            result="Secret"
        )
        
        resp = dispatcher.dispatch(req)
        
        self.assertEqual(resp.message_type, MessageType.TASK_BLOCKED)
        self.assertEqual(resp.status, AgentStatus.BLOCKED)
        self.assertEqual(resp.errors[0].code, "PERMISSION_DENIED")

    def test_files_changed_extraction(self):
        agents = {"TargetAgent": MockAgent("TargetAgent")}
        f_change = [{"path": "test.txt", "operation": "created"}]
        audit_events = [
            {"task_id": "n4", "tool": "write", "files_changed": json.dumps(f_change)}
        ]
        logger = MockAuditLogger(audit_events)
        dispatcher = A2ADispatcher(agents, logger)
        
        req = AgentMessage(
            message_id="m4",
            task_id="t4",
            node_id="n4",
            sender_agent="Scheduler",
            recipient_agent="TargetAgent",
            message_type=MessageType.TASK_REQUEST,
            status=AgentStatus.PENDING,
            result="Write file"
        )
        
        resp = dispatcher.dispatch(req)
        self.assertEqual(len(resp.files_changed), 1)
        self.assertEqual(resp.files_changed[0].path, "test.txt")

if __name__ == '__main__':
    unittest.main()
