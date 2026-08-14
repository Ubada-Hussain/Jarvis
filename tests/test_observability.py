import unittest
import time
from core.observability import observability_manager, ObservabilityEvent
from core.execution_gate import ExecutionGate, ToolMetadata, RiskLevel
from core.verification import ToolResult, VerificationStatus

class TestObservability(unittest.TestCase):
    def setUp(self):
        observability_manager.callbacks = []
        observability_manager.events_history = []
        self.received_events = []
        
        def cb(payload):
            self.received_events.append(payload)
            
        observability_manager.register_callback(cb)
        
    def test_observability_manager_lifecycle(self):
        # Start Task
        observability_manager.start_task("task-123", "analyze my code")
        state = observability_manager.get_current_state()
        
        self.assertEqual(state["task_id"], "task-123")
        self.assertEqual(state["status"], "PLANNING")
        
        self.assertTrue(len(self.received_events) > 0)
        last_event = self.received_events[-1]["event"]
        self.assertEqual(last_event["event_type"], "TASK_STARTED")
        
        # Agent Selected
        observability_manager.update_agent("DevAgent")
        state = observability_manager.get_current_state()
        self.assertEqual(state["active_agent"], "DevAgent")
        self.assertEqual(state["status"], "EXECUTING")
        
        # End Task
        observability_manager.end_task(status="COMPLETED")
        state = observability_manager.get_current_state()
        self.assertEqual(state["status"], "COMPLETED")
        
        last_event = self.received_events[-1]["event"]
        self.assertEqual(last_event["event_type"], "TASK_COMPLETED")

    def test_execution_gate_hooks(self):
        # We need a dummy approval manager
        class DummyApproval:
            def require_approval(self, desc):
                return True
        
        gate = ExecutionGate(agent_name="TestAgent", approval_manager=DummyApproval())
        gate.task_id = "test-task"
        
        def dummy_tool(x):
            return ToolResult(message="success", status=VerificationStatus.VERIFIED_SUCCESS, evidence={"x": x})
            
        gate.register(
            func=dummy_tool,
            metadata=ToolMetadata(name="dummy_tool", risk_level=RiskLevel.READ_ONLY, required_permission="none")
        )
        
        # Clear previous events
        self.received_events.clear()
        
        res = gate.execute("dummy_tool", x=42)
        print("EXECUTE RESULT:", res.to_json())
        
        # Verify events were fired
        event_types = [p["event"]["event_type"] for p in self.received_events if p.get("event")]
        
        self.assertIn("TOOL_REQUESTED", event_types)
        self.assertIn("TOOL_STARTED", event_types)
        self.assertIn("TOOL_COMPLETED", event_types)
        
        # Verify TOOL_COMPLETED has correct data
        completion_payload = next(p for p in self.received_events if p["event"]["event_type"] == "TOOL_COMPLETED")
        self.assertEqual(completion_payload["event"]["status"], "EXECUTED")
        self.assertEqual(completion_payload["event"]["verification_status"], "VERIFIED_SUCCESS")
        
if __name__ == '__main__':
    unittest.main()
