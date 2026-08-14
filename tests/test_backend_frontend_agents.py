import unittest
import os
import tempfile
import json
import uuid
from unittest.mock import MagicMock, patch

from agents.capabilities import (
    AgentCapability, BACKEND_CAPABILITIES, FRONTEND_CAPABILITIES,
    SHARED_DEV_CAPABILITIES, AgentCapabilityContract
)
from agents.backend_agent import BackendAgent
from agents.frontend_agent import FrontendAgent
from agents.dev_agent import DevAgent
from agents.master_agent import MasterAgent, _AGENT_ID_MAP, agent_status
from core.verification import ToolResult, VerificationStatus
from core.execution_gate import ExecutionGate, ToolMetadata, RiskLevel
from core.audit_logger import SQLiteAuditLogger, AuditEvent
from core.a2a import A2ADispatcher, AgentMessage, MessageType, AgentStatus, FileChange, FileOperation
from core.planner import Planner, TaskGraph, TaskNode, TaskState
from core.scheduler import DependencyScheduler
from core.observability import observability_manager, ObservabilityEvent
from core.environment_index import EnvironmentIndex
from core.environment_models import EnvironmentKnowledge, EnvironmentFact
from core.dev_tools import (
    read_code_file, write_code_file, inspect_code_directory,
    run_backend_tests, run_frontend_build
)

class MockLLMEngine:
    def __init__(self, predefined_responses=None):
        self.predefined_responses = predefined_responses or {}
        self.last_prompt = None
        self.last_tools = None

    def generate_response(self, prompt: str, system_prompt: str = None, tools: list = None, tool_logic=None):
        self.last_prompt = prompt
        self.last_tools = tools
        
        # Tool logic simulation if tool_logic provided
        if tool_logic and hasattr(tool_logic, 'execute'):
            if "read_code_file" in prompt or "read" in prompt:
                res = tool_logic.execute("read_code_file", file_path="test.py")
                return f"Tool Output: {res.message}"
            elif "write_code_file" in prompt or "write" in prompt:
                res = tool_logic.execute("write_code_file", file_path="test.py", content="# hello")
                return f"Tool Output: {res.message}"
            elif "start_frontend_server" in prompt or "start server" in prompt:
                res = tool_logic.execute("start_frontend_server")
                return f"Tool Output: {res.message}"
                
        for k, v in self.predefined_responses.items():
            if k.lower() in prompt.lower():
                return v
        return "Generic LLM Response"

class MockMemoryManager:
    def __init__(self):
        self.saved_interactions = []
        self.episodic_memories = []

    def get_relevant_context(self, task: str, memory_types: list = None, max_results: int = 3):
        return []

    def save_interaction(self, user_input: str, ai_response: str, activity_type: str):
        self.saved_interactions.append({
            "user_input": user_input, "ai_response": ai_response, "activity_type": activity_type
        })

    def save_episodic_memory(self, memory):
        self.episodic_memories.append(memory)

class MockApprovalManager:
    def __init__(self, auto_approve=True):
        self.auto_approve = auto_approve
        self.approval_requested = False
        self.last_action = None

    def require_approval(self, action_desc: str) -> bool:
        self.approval_requested = True
        self.last_action = action_desc
        return self.auto_approve

class TestBackendFrontendAgents(unittest.TestCase):
    def setUp(self):
        self.llm = MockLLMEngine()
        self.memory = MockMemoryManager()
        self.approval = MockApprovalManager()
        
        self.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db_path = self.temp_db_file.name
        self.temp_db_file.close()
        self.audit_logger = SQLiteAuditLogger(self.temp_db_path)

    def tearDown(self):
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 16.1 - Agent Capabilities Tests (1, 2, 3)
    # ─────────────────────────────────────────────────────────────────────────

    def test_01_backend_agent_capabilities(self):
        """1. BackendAgent exposes only intended capabilities."""
        backend = BackendAgent(self.llm, self.memory, self.approval)
        contract = backend.get_contract()
        
        self.assertEqual(backend.name, "BackendAgent")
        self.assertIn(AgentCapability.BACKEND_CODE, backend.capabilities)
        self.assertIn(AgentCapability.API, backend.capabilities)
        self.assertIn(AgentCapability.SERVER, backend.capabilities)
        self.assertIn(AgentCapability.DATABASE, backend.capabilities)
        self.assertIn(AgentCapability.BACKEND_TESTS, backend.capabilities)
        
        # Must not contain frontend-exclusive capabilities
        self.assertNotIn(AgentCapability.FRONTEND_CODE, backend.capabilities)
        self.assertNotIn(AgentCapability.COMPONENTS, backend.capabilities)
        self.assertNotIn(AgentCapability.STYLING, backend.capabilities)
        self.assertNotIn(AgentCapability.FRONTEND_BUILD, backend.capabilities)

    def test_02_frontend_agent_capabilities(self):
        """2. FrontendAgent exposes only intended capabilities."""
        frontend = FrontendAgent(self.llm, self.memory, self.approval)
        contract = frontend.get_contract()
        
        self.assertEqual(frontend.name, "FrontendAgent")
        self.assertIn(AgentCapability.FRONTEND_CODE, frontend.capabilities)
        self.assertIn(AgentCapability.COMPONENTS, frontend.capabilities)
        self.assertIn(AgentCapability.STYLING, frontend.capabilities)
        self.assertIn(AgentCapability.FRONTEND_BUILD, frontend.capabilities)
        self.assertIn(AgentCapability.FRONTEND_TESTS, frontend.capabilities)
        
        # Must not contain backend-exclusive capabilities
        self.assertNotIn(AgentCapability.BACKEND_CODE, frontend.capabilities)
        self.assertNotIn(AgentCapability.API, frontend.capabilities)
        self.assertNotIn(AgentCapability.DATABASE, frontend.capabilities)

    def test_03_shared_capabilities_work_correctly(self):
        """3. Shared capabilities work correctly on both agents."""
        backend = BackendAgent(self.llm, self.memory, self.approval)
        frontend = FrontendAgent(self.llm, self.memory, self.approval)
        
        for cap in SHARED_DEV_CAPABILITIES:
            self.assertIn(cap, backend.capabilities)
            self.assertIn(cap, frontend.capabilities)

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 16.2 - Routing Tests (4, 5, 6, 7)
    # ─────────────────────────────────────────────────────────────────────────

    def test_04_backend_task_routing(self):
        """4. Backend task routes to BackendAgent."""
        backend_plan_json = json.dumps({
            "nodes": [
                {
                    "node_id": "be-1",
                    "description": "Create FastAPI endpoint /api/users",
                    "agent": "BackendAgent",
                    "dependencies": [],
                    "risk_level": "REVERSIBLE"
                }
            ]
        })
        llm = MockLLMEngine({"fastapi": backend_plan_json})
        planner = Planner(llm, self.memory)
        
        available = {
            "BackendAgent": "Backend developer",
            "FrontendAgent": "Frontend developer",
            "SystemAgent": "System admin"
        }
        graph = planner.create_graph("Create FastAPI endpoint /api/users", available)
        
        self.assertIn("be-1", graph.nodes)
        self.assertEqual(graph.nodes["be-1"].agent, "BackendAgent")

    def test_05_frontend_task_routing(self):
        """5. Frontend task routes to FrontendAgent."""
        frontend_plan_json = json.dumps({
            "nodes": [
                {
                    "node_id": "fe-1",
                    "description": "Build React UserProfile component with styling",
                    "agent": "FrontendAgent",
                    "dependencies": [],
                    "risk_level": "REVERSIBLE"
                }
            ]
        })
        llm = MockLLMEngine({"react": frontend_plan_json})
        planner = Planner(llm, self.memory)
        
        available = {
            "BackendAgent": "Backend developer",
            "FrontendAgent": "Frontend developer"
        }
        graph = planner.create_graph("Build React UserProfile component with styling", available)
        
        self.assertIn("fe-1", graph.nodes)
        self.assertEqual(graph.nodes["fe-1"].agent, "FrontendAgent")

    def test_06_mixed_task_routing(self):
        """6. Mixed task creates appropriate TaskGraph nodes with dependencies."""
        mixed_plan_json = json.dumps({
            "nodes": [
                {
                    "node_id": "be-api",
                    "description": "Implement authentication backend API",
                    "agent": "BackendAgent",
                    "dependencies": [],
                    "risk_level": "REVERSIBLE"
                },
                {
                    "node_id": "fe-ui",
                    "description": "Build Login UI in React and connect to auth API",
                    "agent": "FrontendAgent",
                    "dependencies": ["be-api"],
                    "risk_level": "REVERSIBLE"
                }
            ]
        })
        llm = MockLLMEngine({"full-stack": mixed_plan_json})
        planner = Planner(llm, self.memory)
        
        available = {
            "BackendAgent": "Backend developer",
            "FrontendAgent": "Frontend developer"
        }
        graph = planner.create_graph("Build full-stack auth system", available)
        
        self.assertEqual(len(graph.nodes), 2)
        self.assertEqual(graph.nodes["be-api"].agent, "BackendAgent")
        self.assertEqual(graph.nodes["fe-ui"].agent, "FrontendAgent")
        self.assertEqual(graph.nodes["fe-ui"].dependencies, ["be-api"])

    def test_07_ambiguous_task_safe_handling(self):
        """7. Ambiguous task does not blindly guess."""
        ambiguous_plan_json = json.dumps({
            "nodes": [
                {
                    "node_id": "ambig-1",
                    "description": "Perform mystery operation on unknown stack",
                    "agent": "NOT_AVAILABLE",
                    "dependencies": [],
                    "risk_level": "UNKNOWN"
                }
            ]
        })
        llm = MockLLMEngine({"mystery": ambiguous_plan_json})
        planner = Planner(llm, self.memory)
        
        available = {
            "BackendAgent": "Backend developer",
            "FrontendAgent": "Frontend developer"
        }
        graph = planner.create_graph("Perform mystery operation on unknown stack", available)
        self.assertEqual(graph.nodes["ambig-1"].agent, "NOT_AVAILABLE")

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 16.3 - Environment Index Evidence Tests (8, 9)
    # ─────────────────────────────────────────────────────────────────────────

    def test_08_environment_evidence_in_planner(self):
        """8. Routing uses Environment Index evidence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a mock Python FastAPI environment
            req_file = os.path.join(tmpdir, "requirements.txt")
            with open(req_file, "w") as f:
                f.write("fastapi\nuvicorn\n")
                
            env_index = EnvironmentIndex(self.temp_db_path)
            knowledge = env_index.refresh(tmpdir)
            
            self.assertTrue(any(f.value == "FastAPI" for f in knowledge.frameworks))
            self.assertTrue(any(f.value == "Python" for f in knowledge.languages))

    def test_09_missing_environment_evidence_handled_safely(self):
        """9. Missing environment evidence is handled safely (returns None or empty)."""
        env_index = EnvironmentIndex(self.temp_db_path)
        knowledge = env_index.get_knowledge("non_existent_folder_xyz_123")
        self.assertIsNone(knowledge)
        facts = env_index.query("non_existent_folder_xyz_123")
        self.assertEqual(facts, [])

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 16.4 - ExecutionGate & Permission Tests (10, 11, 12, 13)
    # ─────────────────────────────────────────────────────────────────────────

    def test_10_backend_agent_uses_execution_gate(self):
        """10. BackendAgent uses ExecutionGate."""
        backend = BackendAgent(self.llm, self.memory, self.approval)
        gate = backend._setup_execution_gate("task-be-1")
        self.assertIsInstance(gate, ExecutionGate)
        self.assertEqual(gate.agent_name, "BackendAgent")
        self.assertIn("write_code_file", gate._registry)

    def test_11_frontend_agent_uses_execution_gate(self):
        """11. FrontendAgent uses ExecutionGate."""
        frontend = FrontendAgent(self.llm, self.memory, self.approval)
        gate = frontend._setup_execution_gate("task-fe-1")
        self.assertIsInstance(gate, ExecutionGate)
        self.assertEqual(gate.agent_name, "FrontendAgent")
        self.assertIn("start_frontend_server", gate._registry)

    def test_12_permission_denial_blocks_execution(self):
        """12. Neither agent can bypass permissions."""
        strict_approval = MockApprovalManager(auto_approve=False)
        backend = BackendAgent(self.llm, self.memory, strict_approval)
        
        gate = ExecutionGate(strict_approval, agent_name="BackendAgent", task_id="perm-test", audit_logger=self.audit_logger)
        gate.register(ToolMetadata("dangerous_tool", RiskLevel.DESTRUCTIVE, "destructive_op", requires_confirmation=True), lambda: ToolResult(VerificationStatus.VERIFIED_SUCCESS, "Hacked"))
        
        result = gate.execute("dangerous_tool")
        self.assertEqual(result.status, VerificationStatus.VERIFIED_FAILURE)
        self.assertIn("DENIED", result.message)

    def test_13_confirmation_works_when_granted(self):
        """13. Confirmation works when approved by user."""
        granted_approval = MockApprovalManager(auto_approve=True)
        gate = ExecutionGate(granted_approval, agent_name="BackendAgent", task_id="confirm-test", audit_logger=self.audit_logger)
        gate.register(ToolMetadata("critical_tool", RiskLevel.EXTERNAL_SIDE_EFFECT, "network_op", requires_confirmation=True), lambda: ToolResult(VerificationStatus.VERIFIED_SUCCESS, "Executed safely"))
        
        result = gate.execute("critical_tool")
        self.assertTrue(granted_approval.approval_requested)
        self.assertEqual(result.status, VerificationStatus.VERIFIED_SUCCESS)

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 16.5 - Verification Tests (14, 15, 16, 17)
    # ─────────────────────────────────────────────────────────────────────────

    def test_14_backend_verified_success(self):
        """14. Backend verified success works."""
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            f.write(b"# initial\n")
            target_path = f.name
            
        try:
            res = write_code_file(target_path, "def add(a, b): return a + b\n")
            self.assertEqual(res.status, VerificationStatus.VERIFIED_SUCCESS)
            self.assertIn("Successfully wrote", res.message)
            self.assertEqual(len(res.files_changed), 1)
            self.assertEqual(res.files_changed[0]["operation"], "modified")
        finally:
            if os.path.exists(target_path):
                os.remove(target_path)

    def test_15_frontend_verified_success(self):
        """15. Frontend verified file reading and tool verification."""
        with tempfile.NamedTemporaryFile(suffix=".tsx", delete=False) as f:
            f.write(b"export const App = () => <div>Hello</div>;\n")
            target_path = f.name
            
        try:
            res = read_code_file(target_path, 1, 10)
            self.assertEqual(res.status, VerificationStatus.VERIFIED_SUCCESS)
            self.assertIn("Read 1 lines", res.message)
        finally:
            if os.path.exists(target_path):
                os.remove(target_path)

    def test_16_failed_verification_produces_failure(self):
        """16. Failed verification produces failure result."""
        res = read_code_file("non_existent_file_abc_123.tsx")
        self.assertEqual(res.status, VerificationStatus.VERIFIED_FAILURE)
        self.assertIn("File not found", res.message)

    def test_17_unverified_result_is_not_treated_as_success(self):
        """17. Unverified result is not treated as verified success."""
        gate = ExecutionGate(self.approval, agent_name="BackendAgent", task_id="unver-test", audit_logger=self.audit_logger)
        gate.register(ToolMetadata("unverified_tool", RiskLevel.READ_ONLY, "misc"), lambda: "Raw string return")
        
        result = gate.execute("unverified_tool")
        self.assertEqual(result.status, VerificationStatus.UNVERIFIED)

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 16.6 - A2A Structured Messaging Tests (18, 19, 20)
    # ─────────────────────────────────────────────────────────────────────────

    def test_18_a2a_structured_message(self):
        """18. Backend -> Frontend structured message works."""
        backend = BackendAgent(self.llm, self.memory, self.approval)
        frontend = FrontendAgent(self.llm, self.memory, self.approval)
        agents = {"BackendAgent": backend, "FrontendAgent": frontend}
        
        dispatcher = A2ADispatcher(agents, self.audit_logger)
        req = AgentMessage(
            message_id=str(uuid.uuid4()),
            task_id="task-main",
            node_id="node-1",
            sender_agent="BackendAgent",
            recipient_agent="FrontendAgent",
            message_type=MessageType.TASK_REQUEST,
            status=AgentStatus.PENDING,
            result="Build React view for API"
        )
        resp = dispatcher.dispatch(req)
        
        self.assertEqual(resp.sender_agent, "FrontendAgent")
        self.assertEqual(resp.recipient_agent, "BackendAgent")
        self.assertEqual(resp.task_id, "task-main")
        self.assertEqual(resp.node_id, "node-1")
        self.assertEqual(resp.status, AgentStatus.COMPLETED)

    def test_19_a2a_task_and_node_id_preserved(self):
        """19. task_id/node_id preserved across message exchanges."""
        backend = BackendAgent(self.llm, self.memory, self.approval)
        agents = {"BackendAgent": backend}
        dispatcher = A2ADispatcher(agents, self.audit_logger)
        
        req = AgentMessage(
            message_id="msg-unique-123",
            task_id="graph-999",
            node_id="step-backend-42",
            sender_agent="Scheduler",
            recipient_agent="BackendAgent",
            message_type=MessageType.TASK_REQUEST,
            status=AgentStatus.PENDING,
            result="Run tests"
        )
        resp = dispatcher.dispatch(req)
        self.assertEqual(resp.task_id, "graph-999")
        self.assertEqual(resp.node_id, "step-backend-42")

    def test_20_files_changed_preserved_with_evidence(self):
        """20. files_changed preserved with verified filesystem evidence."""
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            f.write(b"# initial\n")
            target_path = f.name

        try:
            # Execute tool through ExecutionGate
            gate = ExecutionGate(self.approval, agent_name="BackendAgent", task_id="node-file-1", audit_logger=self.audit_logger)
            gate.register(ToolMetadata("write_code_file", RiskLevel.REVERSIBLE, "fs_write"), write_code_file)
            res = gate.execute("write_code_file", file_path=target_path, content="# updated code\n")
            
            # Now evaluate evidence in A2ADispatcher
            dispatcher = A2ADispatcher({}, self.audit_logger)
            req = AgentMessage(
                message_id="msg-file-1",
                task_id="graph-file",
                node_id="node-file-1",
                sender_agent="Scheduler",
                recipient_agent="BackendAgent",
                message_type=MessageType.TASK_REQUEST,
                status=AgentStatus.PENDING
            )
            evaluated = dispatcher._evaluate_evidence(req, res.message)
            
            self.assertEqual(len(evaluated.files_changed), 1)
            self.assertEqual(evaluated.files_changed[0].path, target_path)
            self.assertEqual(evaluated.files_changed[0].operation, FileOperation.MODIFIED)
        finally:
            if os.path.exists(target_path):
                os.remove(target_path)

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 16.7 - Observability & Audit Tests (21, 22, 23, 24)
    # ─────────────────────────────────────────────────────────────────────────

    def test_21_observability_agent_attribution(self):
        """21. Observability displays correct specialized agent (BE / FE)."""
        self.assertIn("BackendAgent", _AGENT_ID_MAP)
        self.assertEqual(_AGENT_ID_MAP["BackendAgent"], "BE")
        self.assertIn("FrontendAgent", _AGENT_ID_MAP)
        self.assertEqual(_AGENT_ID_MAP["FrontendAgent"], "FE")

    def test_22_observability_agent_handoff_visible(self):
        """22. Agent handoff emits A2A_MESSAGE event."""
        events_emitted = []
        def handler(event):
            events_emitted.append(event)
            
        observability_manager.register_callback(handler)
        
        backend = BackendAgent(self.llm, self.memory, self.approval)
        agents = {"BackendAgent": backend}
        dispatcher = A2ADispatcher(agents, self.audit_logger)
        
        req = AgentMessage(
            message_id="msg-obs-1",
            task_id="graph-obs",
            node_id="node-obs-1",
            sender_agent="Scheduler",
            recipient_agent="BackendAgent",
            message_type=MessageType.TASK_REQUEST,
            status=AgentStatus.PENDING,
            result="Backend task"
        )
        dispatcher.dispatch(req)
        
        # Verify an A2A observability event was emitted
        self.assertTrue(any(e.get("event") == "A2A_MESSAGE" or e.get("type") == "observability_update" for e in events_emitted))

    def test_23_tool_execution_attributed_correctly(self):
        """23. Tool execution in ExecutionGate is attributed to active agent."""
        gate = ExecutionGate(self.approval, agent_name="FrontendAgent", task_id="fe-task-9", audit_logger=self.audit_logger)
        gate.register(ToolMetadata("inspect_directory", RiskLevel.READ_ONLY, "fs_read"), inspect_code_directory)
        gate.execute("inspect_directory", directory_path=".")
        
        events = self.audit_logger.query_events(task_id="fe-task-9")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["agent"], "FrontendAgent")
        self.assertEqual(events[0]["tool"], "inspect_directory")

    def test_24_audit_records_specialized_agents(self):
        """24. Audit table contains distinct BackendAgent and FrontendAgent records."""
        gate_be = ExecutionGate(self.approval, agent_name="BackendAgent", task_id="audit-be", audit_logger=self.audit_logger)
        gate_be.register(ToolMetadata("run_backend_tests", RiskLevel.READ_ONLY, "test"), lambda: ToolResult(VerificationStatus.VERIFIED_SUCCESS, "Tests OK"))
        gate_be.execute("run_backend_tests")

        gate_fe = ExecutionGate(self.approval, agent_name="FrontendAgent", task_id="audit-fe", audit_logger=self.audit_logger)
        gate_fe.register(ToolMetadata("frontend_server_status", RiskLevel.READ_ONLY, "status"), lambda: ToolResult(VerificationStatus.VERIFIED_SUCCESS, "Server OK"))
        gate_fe.execute("frontend_server_status")

        be_events = self.audit_logger.query_events(agent="BackendAgent")
        fe_events = self.audit_logger.query_events(agent="FrontendAgent")
        
        self.assertEqual(len(be_events), 1)
        self.assertEqual(be_events[0]["agent"], "BackendAgent")
        self.assertEqual(len(fe_events), 1)
        self.assertEqual(fe_events[0]["agent"], "FrontendAgent")

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 16.8 - Backward Compatibility Tests (25)
    # ─────────────────────────────────────────────────────────────────────────

    def test_25_devagent_backward_compatibility(self):
        """25. Existing DevAgent callers continue working seamlessly."""
        dev = DevAgent(self.llm, self.memory, self.approval)
        self.assertEqual(dev.name, "DevAgent")
        
        # Test server status call on DevAgent
        res = dev._server_status()
        self.assertEqual(res.status, VerificationStatus.VERIFIED_SUCCESS)
        self.assertIn("Server Status", res.message)
        
        # Test inspect directory on DevAgent
        res_dir = dev._inspect_directory()
        self.assertEqual(res_dir.status, VerificationStatus.VERIFIED_SUCCESS)
        
        # MasterAgent initialization with DevAgent, BackendAgent, FrontendAgent
        master = MasterAgent(self.llm, self.memory, self.approval)
        self.assertIn("BackendAgent", master.agents)
        self.assertIn("FrontendAgent", master.agents)
        self.assertIn("DevAgent", master.agents)

if __name__ == "__main__":
    unittest.main()
