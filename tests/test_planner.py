import unittest
import time
from core.planner import Planner, TaskGraph, TaskNode, TaskState
from core.scheduler import DependencyScheduler

class MockLLMEngine:
    def __init__(self, response_text):
        self.response_text = response_text
    def generate_response(self, **kwargs):
        return self.response_text

class MockAgent:
    def __init__(self, name):
        self.name = name
        self.called = False
        self.call_count = 0
        self.sleep = 0
        
    def execute(self, task: str, task_id: str = None) -> str:
        self.called = True
        self.call_count += 1
        if self.sleep:
            time.sleep(self.sleep)
        if "FAIL" in task:
            raise Exception("Agent failed intentionally")
        return f"Mock result for {task}"

class MockAuditLogger:
    def __init__(self, events):
        self.events = events
        self.a2a_log = []
    def query_events(self, task_id=None, **kwargs):
        return [e for e in self.events if e.get("task_id") == task_id]
    def log_a2a_message(self, message):
        self.a2a_log.append(message)

class TestPlannerAndScheduler(unittest.TestCase):
    def test_planner_parsing(self):
        json_resp = '''
        {
          "nodes": [
            {
               "node_id": "n1",
               "description": "Task 1",
               "agent": "MockAgent",
               "dependencies": []
            },
            {
               "node_id": "n2",
               "description": "Task 2",
               "agent": "MockAgent",
               "dependencies": ["n1"]
            }
          ]
        }
        '''
        planner = Planner(MockLLMEngine(json_resp))
        graph = planner.create_graph("Do stuff", {"MockAgent": "Desc"})
        
        self.assertEqual(len(graph.nodes), 2)
        self.assertEqual(graph.nodes["n2"].dependencies, ["n1"])
        
    def test_planner_cyclic_detection(self):
        json_resp = '''
        {
          "nodes": [
            {"node_id": "A", "description": "1", "agent": "MockAgent", "dependencies": ["B"]},
            {"node_id": "B", "description": "2", "agent": "MockAgent", "dependencies": ["A"]}
          ]
        }
        '''
        planner = Planner(MockLLMEngine(json_resp))
        # This should fail parsing and fallback to a safe 1-node graph because of the cycle
        graph = planner.create_graph("Do stuff", {"MockAgent": "Desc", "SystemAgent": "Desc"})
        # Should fallback to SystemAgent single node
        self.assertEqual(len(graph.nodes), 1)
        
    def test_scheduler_execution(self):
        # A -> B
        graph = TaskGraph(graph_id="g1", objective="Test")
        graph.nodes["A"] = TaskNode(node_id="A", description="Task A", agent="MockAgent1", dependencies=[])
        graph.nodes["B"] = TaskNode(node_id="B", description="Task B", agent="MockAgent2", dependencies=["A"])
        
        agents = {
            "MockAgent1": MockAgent("MockAgent1"),
            "MockAgent2": MockAgent("MockAgent2")
        }
        
        # Give MockAgent1 a VERIFIED_SUCCESS tool result in audit log
        audit_events = [
            {"task_id": "A", "verification_status": "VERIFIED_SUCCESS"},
            {"task_id": "B", "verification_status": "VERIFIED_SUCCESS"}
        ]
        
        scheduler = DependencyScheduler(agents, MockAuditLogger(audit_events))
        scheduler.execute_graph(graph)
        
        self.assertEqual(graph.nodes["A"].status, TaskState.COMPLETED)
        self.assertEqual(graph.nodes["B"].status, TaskState.COMPLETED)
        self.assertTrue(agents["MockAgent1"].called)
        self.assertTrue(agents["MockAgent2"].called)

    def test_scheduler_failure_blocks_downstream(self):
        # A -> B
        graph = TaskGraph(graph_id="g2", objective="Test")
        # Task A will fail
        graph.nodes["A"] = TaskNode(node_id="A", description="Task A", agent="MockAgent1", dependencies=[])
        graph.nodes["B"] = TaskNode(node_id="B", description="Task B", agent="MockAgent2", dependencies=["A"])
        
        agents = {
            "MockAgent1": MockAgent("MockAgent1"),
            "MockAgent2": MockAgent("MockAgent2")
        }
        
        # A fails verification
        audit_events = [
            {"task_id": "A", "verification_status": "VERIFIED_FAILURE", "error": "Something went wrong"}
        ]
        
        scheduler = DependencyScheduler(agents, MockAuditLogger(audit_events))
        scheduler.execute_graph(graph)
        
        self.assertEqual(graph.nodes["A"].status, TaskState.FAILED)
        # B should be BLOCKED because A failed
        self.assertEqual(graph.nodes["B"].status, TaskState.BLOCKED)
        self.assertTrue(agents["MockAgent1"].called)
        self.assertFalse(agents["MockAgent2"].called)

if __name__ == '__main__':
    unittest.main()
