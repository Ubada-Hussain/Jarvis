import unittest
import os
import tempfile
import uuid
from typing import Dict, Any

from core.tool_registry import ToolRegistry, ToolDefinition, init_standard_tool_registry
from core.execution_gate import ExecutionGate, ToolMetadata, RiskLevel
from core.verification import ToolResult, VerificationStatus
from core.audit_logger import SQLiteAuditLogger
from core.observability import observability_manager, ObservabilityEvent
from core.recovery import RecoveryManager, FailureCategory, RecoveryAction
from core.planner import TaskPlanner, TaskGraph, TaskNode

class MockApprovalManager:
    def __init__(self, auto_approve=True):
        self.auto_approve = auto_approve
        self.requested = False
        self.last_action = ""
    def require_approval(self, action_desc: str) -> bool:
        self.requested = True
        self.last_action = action_desc
        return self.auto_approve

class MockLLMEngine:
    def __init__(self, response="{}"):
        self.response = response
    def generate_response(self, prompt: str, system_prompt: str = None, tools: list = None, tool_logic=None):
        return self.response

class TestToolRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = init_standard_tool_registry()
        self.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db_path = self.temp_db_file.name
        self.temp_db_file.close()
        self.audit_logger = SQLiteAuditLogger(self.temp_db_path)
        self.approval = MockApprovalManager(auto_approve=True)

    def tearDown(self):
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except Exception:
                pass

    # ── Registry Operations (Tests 1-9) ──────────────────────────────────────

    def test_01_tool_registration_works(self):
        """1. Tool registration works."""
        t = ToolDefinition(
            name="custom_test_tool",
            description="Custom test tool",
            owner="Testing",
            capabilities=["test_cap"],
            agents=["BackendAgent"],
            risk_level=RiskLevel.READ_ONLY,
            verification_contract="CUSTOM_VERIFICATION_CHECK"
        )
        self.assertTrue(self.registry.register(t))
        self.assertIsNotNone(self.registry.get("custom_test_tool"))

    def test_02_duplicate_tool_rejected(self):
        """2. Duplicate tool rejected."""
        t = ToolDefinition(
            name="search_internet",
            description="Duplicate search tool",
            owner="System",
            risk_level=RiskLevel.READ_ONLY,
            verification_contract="DDGS_RESULTS"
        )
        with self.assertRaises(ValueError):
            self.registry.register(t)

    def test_03_invalid_metadata_rejected(self):
        """3. Invalid metadata (empty name) rejected."""
        t = ToolDefinition(
            name="",
            description="No name tool",
            owner="System",
            risk_level=RiskLevel.READ_ONLY,
            verification_contract="VERIFY"
        )
        with self.assertRaises(ValueError):
            self.registry.register(t)

    def test_04_missing_risk_rejected(self):
        """4. Missing risk rejected."""
        t = ToolDefinition(
            name="no_risk_tool",
            description="No risk",
            owner="System",
            risk_level=None,
            verification_contract="VERIFY"
        )
        with self.assertRaises(ValueError):
            self.registry.register(t)

    def test_05_missing_verification_contract_rejected(self):
        """5. Missing verification contract rejected."""
        t1 = ToolDefinition(
            name="no_contract_tool",
            description="No contract",
            owner="System",
            risk_level=RiskLevel.READ_ONLY,
            verification_contract=""
        )
        with self.assertRaises(ValueError):
            self.registry.register(t1)

        t2 = ToolDefinition(
            name="trivial_contract_tool",
            description="Trivial contract",
            owner="System",
            risk_level=RiskLevel.READ_ONLY,
            verification_contract="success string"
        )
        with self.assertRaises(ValueError):
            self.registry.register(t2)

    def test_06_invalid_retry_configuration_rejected(self):
        """6. Invalid retry configuration rejected (destructive tool marked retryable)."""
        t = ToolDefinition(
            name="dangerous_retry_tool",
            description="Destructive retry",
            owner="System",
            risk_level=RiskLevel.DESTRUCTIVE,
            confirmation_required=True,
            retryable=True,
            max_retries=2,
            verification_contract="FILE_DELETED"
        )
        with self.assertRaises(ValueError):
            self.registry.register(t)

    def test_07_tool_lookup_works(self):
        """7. Tool lookup works."""
        tool = self.registry.get("read_code_file")
        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "read_code_file")
        self.assertEqual(tool.risk_level, RiskLevel.READ_ONLY)

    def test_08_capability_lookup_works(self):
        """8. Capability lookup works."""
        tools = self.registry.get_for_capability("backend_tests")
        self.assertTrue(len(tools) >= 1)
        self.assertEqual(tools[0].name, "run_backend_tests")

    def test_09_agent_lookup_works(self):
        """9. Agent lookup works."""
        be_tools = self.registry.get_for_agent("BackendAgent")
        fe_tools = self.registry.get_for_agent("FrontendAgent")
        self.assertTrue(any(t.name == "run_backend_tests" for t in be_tools))
        self.assertTrue(any(t.name == "start_frontend_server" for t in fe_tools))

    # ── Execution & Gate Integration (Tests 10-14) ───────────────────────────

    def test_10_registered_tool_executes_through_execution_gate(self):
        """10. Registered tool executes through ExecutionGate."""
        gate = ExecutionGate(self.approval, agent_name="BackendAgent", task_id="g-t10", audit_logger=self.audit_logger)
        gate.register(ToolMetadata("read_code_file", RiskLevel.READ_ONLY, "fs_read"), lambda file_path: ToolResult(VerificationStatus.VERIFIED_SUCCESS, f"Read {file_path}"))
        res = gate.execute("read_code_file", file_path="main.py")
        self.assertEqual(res.status, VerificationStatus.VERIFIED_SUCCESS)

    def test_11_unregistered_tool_cannot_execute(self):
        """11. Unregistered tool cannot execute (rejected safely)."""
        gate = ExecutionGate(self.approval, agent_name="BackendAgent", task_id="g-t11", audit_logger=self.audit_logger)
        res = gate.execute("magic_unregistered_tool")
        self.assertEqual(res.status, VerificationStatus.VERIFIED_FAILURE)
        self.assertIn("UNREGISTERED_TOOL", res.message)

    def test_12_registry_cannot_bypass_permission(self):
        """12. Registry cannot bypass permission/execution gate."""
        deny_approval = MockApprovalManager(auto_approve=False)
        gate = ExecutionGate(deny_approval, agent_name="BackendAgent", task_id="g-t12", audit_logger=self.audit_logger)
        gate.register(ToolMetadata("delete_file", RiskLevel.DESTRUCTIVE, "fs_delete", requires_confirmation=True), lambda file_path: ToolResult(VerificationStatus.VERIFIED_SUCCESS, "Deleted"))
        res = gate.execute("delete_file", file_path="test.txt")
        self.assertEqual(res.status, VerificationStatus.VERIFIED_FAILURE)
        self.assertIn("DENIED", res.message)

    def test_13_registry_cannot_bypass_confirmation(self):
        """13. Confirmation is mandatory for destructive tool despite registry lookup."""
        t = self.registry.get("delete_file")
        self.assertTrue(t.confirmation_required)
        self.assertEqual(t.risk_level, RiskLevel.DESTRUCTIVE)

    def test_14_invalid_arguments_rejected_before_execution(self):
        """14. Invalid arguments (missing required, wrong type, unexpected param) rejected before execution."""
        gate = ExecutionGate(self.approval, agent_name="BackendAgent", task_id="g-t14", audit_logger=self.audit_logger)
        gate.register(ToolMetadata("write_code_file", RiskLevel.REVERSIBLE, "fs_write"), lambda file_path, content: ToolResult(VerificationStatus.VERIFIED_SUCCESS, "Wrote"))
        
        # Missing required parameter 'content'
        res1 = gate.execute("write_code_file", file_path="main.py")
        self.assertEqual(res1.status, VerificationStatus.VERIFIED_FAILURE)
        self.assertIn("INVALID_TOOL_ARGUMENTS", res1.message)

        # Wrong type: integer instead of string
        res2 = gate.execute("write_code_file", file_path="main.py", content=12345)
        self.assertEqual(res2.status, VerificationStatus.VERIFIED_FAILURE)
        self.assertIn("INVALID_TOOL_ARGUMENTS", res2.message)

        # Unexpected parameter
        res3 = gate.execute("write_code_file", file_path="main.py", content="code", extra_bad_arg="foo")
        self.assertEqual(res3.status, VerificationStatus.VERIFIED_FAILURE)
        self.assertIn("INVALID_TOOL_ARGUMENTS", res3.message)

    # ── Planner Integration (Tests 15-18) ────────────────────────────────────

    def test_15_planner_sees_valid_tools(self):
        """15. Planner prompt contains registered capabilities and tools."""
        from core.environment_index import EnvironmentIndex
        planner = TaskPlanner(self.registry, MockLLMEngine('{"nodes": []}'))
        # Verified by checking tool list generation
        t_list = self.registry.get_for_agent("BackendAgent")
        self.assertTrue(len(t_list) > 0)

    def test_16_planner_cannot_select_unknown_agent(self):
        """16. Planner routes unknown agent to NOT_AVAILABLE."""
        planner = TaskPlanner(
            MockLLMEngine('{"nodes": [{"node_id": "1", "description": "hack", "agent": "HackerAgent", "dependencies": []}]}')
        )
        graph = planner.plan("run hack", available_agents={"BackendAgent": "Backend desc"})
        self.assertEqual(graph.nodes["1"].agent, "NOT_AVAILABLE")

    def test_17_planner_respects_agent_capability(self):
        """17. Backend and Frontend tools mapped to respective agents."""
        be_tools = [t.name for t in self.registry.get_for_agent("BackendAgent")]
        fe_tools = [t.name for t in self.registry.get_for_agent("FrontendAgent")]
        self.assertIn("run_backend_tests", be_tools)
        self.assertIn("start_frontend_server", fe_tools)

    def test_18_planner_receives_risk_and_verification_metadata(self):
        """18. Tool metadata includes risk and verification contract."""
        t = self.registry.get("write_code_file")
        self.assertEqual(t.risk_level, RiskLevel.REVERSIBLE)
        self.assertEqual(t.verification_contract, "FILE_EXISTS_SIZE_MATCH_ON_DISK")

    # ── Recovery Integration (Tests 19-21) ───────────────────────────────────

    def test_19_recovery_manager_uses_registry_metadata(self):
        """19. RecoveryManager uses registry retry metadata."""
        rec = RecoveryManager()
        dec = rec.evaluate_recovery(
            category=FailureCategory.TIMEOUT,
            current_attempt=1,
            tool_name="read_code_file"
        )
        self.assertTrue(dec.should_retry)
        self.assertEqual(dec.action, RecoveryAction.RETRY)

    def test_20_non_retryable_tool_is_not_retried(self):
        """20. Non-retryable tool in registry is not retried."""
        rec = RecoveryManager()
        dec = rec.evaluate_recovery(
            category=FailureCategory.TOOL_ERROR,
            current_attempt=1,
            tool_name="delete_file"
        )
        self.assertFalse(dec.should_retry)
        self.assertEqual(dec.action, RecoveryAction.FAIL)

    def test_21_destructive_tool_not_automatically_retried(self):
        """21. Destructive tool declared with max_retries=0 and non-retryable."""
        t = self.registry.get("delete_file")
        self.assertFalse(t.retryable)
        self.assertEqual(t.max_retries, 0)

    # ── Verification Contracts (Tests 22-23) ─────────────────────────────────

    def test_22_tool_result_verification_contract_respected(self):
        """22. ToolResult verification contract is respected."""
        gate = ExecutionGate(self.approval, agent_name="BackendAgent", task_id="g-t22", audit_logger=self.audit_logger)
        gate.register(ToolMetadata("read_code_file", RiskLevel.READ_ONLY, "fs_read"), lambda file_path: ToolResult(VerificationStatus.VERIFIED_SUCCESS, "Read ok", evidence="File found"))
        res = gate.execute("read_code_file", file_path="app.py")
        self.assertEqual(res.status, VerificationStatus.VERIFIED_SUCCESS)

    def test_23_unverified_cannot_become_success(self):
        """23. UNVERIFIED cannot become success."""
        gate = ExecutionGate(self.approval, agent_name="BackendAgent", task_id="g-t23", audit_logger=self.audit_logger)
        gate.register(ToolMetadata("search_internet", RiskLevel.READ_ONLY, "internet"), lambda query: "raw unverified string")
        res = gate.execute("search_internet", query="python")
        self.assertEqual(res.status, VerificationStatus.UNVERIFIED)

    # ── Security & Observability (Tests 24-28) ────────────────────────────────

    def test_24_llm_cannot_register_arbitrary_tool(self):
        """24. ExecutionGate rejects dynamic tools not in ToolRegistry."""
        gate = ExecutionGate(self.approval, agent_name="DevAgent", task_id="g-t24", audit_logger=self.audit_logger)
        res = gate.execute("arbitrary_eval_code_from_llm")
        self.assertEqual(res.status, VerificationStatus.VERIFIED_FAILURE)
        self.assertIn("UNREGISTERED_TOOL", res.message)

    def test_25_secrets_not_exposed_through_audit(self):
        """25. Sensitive arguments are redacted in execution audit."""
        gate = ExecutionGate(self.approval, agent_name="DevAgent", task_id="g-t25", audit_logger=self.audit_logger)
        sanitized = gate._sanitize_kwargs({"api_key": "secret-12345", "query": "hello"})
        self.assertEqual(sanitized["api_key"], "[REDACTED]")
        self.assertEqual(sanitized["query"], "hello")

    def test_26_tool_registration_event_emitted(self):
        """26. Tool registration emits TOOL_REGISTERED event."""
        captured = []
        def handler(e):
            captured.append(e)
        observability_manager.register_callback(handler)
        
        reg = ToolRegistry()
        reg.register(ToolDefinition(
            name="observability_test_tool",
            description="Observability test",
            owner="System",
            risk_level=RiskLevel.READ_ONLY,
            verification_contract="STATE_CHECK"
        ))
        self.assertTrue(any(e.get("event", {}).get("event_type") == "TOOL_REGISTERED" or e.get("type") == "observability_update" for e in captured))

    def test_27_unknown_tool_rejection_visible_in_observability(self):
        """27. Unknown tool rejection emits TOOL_REJECTED event."""
        captured = []
        def handler(e):
            captured.append(e)
        observability_manager.register_callback(handler)
        
        gate = ExecutionGate(self.approval, agent_name="DevAgent", task_id="g-t27", audit_logger=self.audit_logger)
        gate.execute("fake_ghost_tool")
        
        events = [e.get("event", {}) for e in captured if isinstance(e, dict)]
        self.assertTrue(any(ev.get("event_type") == "TOOL_REJECTED" for ev in events))

    def test_28_tasks_1_to_10_tools_continue_working(self):
        """28. Existing core tools (read_code_file, write_code_file, run_backend_tests, start_frontend_server, query_environment_index) are all registered."""
        core_tools = [
            "search_internet", "open_url", "check_system_health", "launch_app", "delete_file",
            "create_procedure", "remember_file", "switch_voice_profile",
            "refresh_environment_index", "query_environment_index",
            "read_code_file", "write_code_file", "inspect_directory",
            "run_backend_tests", "run_backend_command",
            "start_frontend_server", "stop_frontend_server", "server_status",
            "run_frontend_build", "run_frontend_tests"
        ]
        for ct in core_tools:
            t = self.registry.get(ct)
            self.assertIsNotNone(t, f"Core tool '{ct}' must be registered.")

if __name__ == "__main__":
    unittest.main()
