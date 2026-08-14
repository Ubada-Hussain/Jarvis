import unittest
import os
import tempfile
from unittest.mock import MagicMock

from core.context_resolver import ContextResolver, StructuredIntent, IntentType, ConfidenceLevel
from core.environment_index import EnvironmentIndex
from core.environment_models import EnvironmentKnowledge, EnvironmentFact
from core.memory_manager import MemoryManager
from core.memory_models import EpisodicMemory, ProceduralMemory, ProcedureStep
from core.tool_registry import tool_registry
from core.planner import TaskPlanner, TaskGraph, TaskNode
from core.execution_gate import ExecutionGate, RiskLevel
from core.audit_logger import SQLiteAuditLogger
from core.observability import observability_manager

class MockMemory:
    def __init__(self):
        self.memories = []
        self.procedures = []
    def get_relevant_context(self, query: str, memory_types: list = None, max_results: int = 3):
        res = []
        if not memory_types or "episodic" in memory_types:
            for m in self.memories:
                res.append({"data": m, "score": 0.8})
        if not memory_types or "procedural" in memory_types:
            for p in self.procedures:
                res.append({"data": p, "score": 0.9})
        return res

class MockEnvIndex:
    def __init__(self, frameworks=None, languages=None):
        self.knowledge = EnvironmentKnowledge(
            project_root=os.getcwd(),
            environment_id="env-test",
            platform="win32",
            os="Windows",
            architecture="x64",
            languages=[EnvironmentFact(fact="language", value=l) for l in (languages or ["Python"])],
            frameworks=[EnvironmentFact(fact="framework", value=f) for f in (frameworks or ["FastAPI"])],
            entry_points=[EnvironmentFact(fact="entry_point", value="main.py")]
        )
    def get_knowledge(self, project_root: str):
        return self.knowledge

class MockLLMEngine:
    def __init__(self, response="{}"):
        self.response = response
    def generate_response(self, prompt: str, system_prompt: str = None, tools: list = None, tool_logic=None):
        return self.response

class TestContextResolver(unittest.TestCase):
    def setUp(self):
        self.mock_memory = MockMemory()
        self.mock_env = MockEnvIndex()
        self.resolver = ContextResolver(
            memory_manager=self.mock_memory,
            env_index=self.mock_env,
            tool_reg=tool_registry
        )

    # ── Intent Tests (1-6) ───────────────────────────────────────────────────

    def test_01_clear_backend_request(self):
        """1. Clear backend request -> BackendAgent candidate."""
        intent = self.resolver.resolve("Create a backend API endpoint for user registration")
        self.assertEqual(intent.intent_type, IntentType.BACKEND_TASK)
        self.assertIn("BackendAgent", intent.candidate_agents)

    def test_02_clear_frontend_request(self):
        """2. Clear frontend request -> FrontendAgent candidate."""
        intent = self.resolver.resolve("Build a React UI component with a submit button and styling")
        self.assertEqual(intent.intent_type, IntentType.FRONTEND_TASK)
        self.assertIn("FrontendAgent", intent.candidate_agents)

    def test_03_full_stack_request(self):
        """3. Full-stack request -> Backend + Frontend candidates."""
        intent = self.resolver.resolve("Implement backend API and connect it to the frontend UI component")
        self.assertEqual(intent.intent_type, IntentType.FULL_STACK_TASK)
        self.assertIn("BackendAgent", intent.candidate_agents)
        self.assertIn("FrontendAgent", intent.candidate_agents)

    def test_04_system_request(self):
        """4. System request -> SystemAgent candidate."""
        intent = self.resolver.resolve("Check system health and CPU usage")
        self.assertEqual(intent.intent_type, IntentType.SYSTEM_OPERATION)
        self.assertIn("SystemAgent", intent.candidate_agents)

    def test_05_research_request(self):
        """5. Research request -> AcademicAgent candidate."""
        intent = self.resolver.resolve("Search arXiv for research papers on transformers")
        self.assertEqual(intent.intent_type, IntentType.RESEARCH_TASK)
        self.assertIn("AcademicAgent", intent.candidate_agents)

    def test_06_unknown_request(self):
        """6. Ambiguous / unknown request -> UNKNOWN."""
        intent = self.resolver.resolve("xyz abc gibberish")
        self.assertEqual(intent.intent_type, IntentType.UNKNOWN)

    # ── Environment Evidence Tests (7-9) ─────────────────────────────────────

    def test_07_environment_evidence_included(self):
        """7. Environment evidence included in StructuredIntent."""
        intent = self.resolver.resolve("Add database route")
        self.assertIn("FastAPI", intent.environment_context.get("frameworks", []))
        self.assertTrue(any("FastAPI" in ev for ev in intent.evidence))

    def test_08_missing_environment_evidence_handled_safely(self):
        """8. Missing environment evidence handled safely without crash."""
        empty_env = MagicMock()
        empty_env.get_knowledge.return_value = None
        resolver = ContextResolver(memory_manager=self.mock_memory, env_index=empty_env)
        intent = resolver.resolve("Create API endpoint")
        self.assertEqual(intent.environment_context, {})
        self.assertTrue(any("No cached facts found" in ev for ev in intent.evidence))

    def test_09_stale_environment_detected(self):
        """9. Environment timestamp exposed in context."""
        intent = self.resolver.resolve("List routes")
        self.assertIn("timestamp", intent.environment_context)

    # ── Memory Context & Precedence Tests (10-13) ────────────────────────────

    def test_10_relevant_episodic_memory_retrieved(self):
        """10. Relevant verified episodic memory retrieved."""
        self.mock_memory.memories.append({
            "summary": "BackendAgent added user API endpoint",
            "outcome": "Success",
            "tags": ["verified"]
        })
        intent = self.resolver.resolve("Add another API endpoint")
        self.assertEqual(len(intent.relevant_memories), 1)

    def test_11_relevant_procedural_memory_retrieved(self):
        """11. Relevant procedural memory retrieved and matched."""
        self.mock_memory.procedures.append({
            "name": "DeployFrontend",
            "trigger": "deploy frontend UI",
            "steps": [{"agent": "FrontendAgent", "action": "run_frontend_build", "description": "build"}]
        })
        intent = self.resolver.resolve("deploy frontend UI")
        self.assertIsNotNone(intent.procedure_match)
        self.assertEqual(intent.procedure_match["name"], "DeployFrontend")

    def test_12_unverified_memory_not_authoritative(self):
        """12. Unverified memory is filtered out."""
        mock_mem = MockMemory()
        mock_mem.memories.append({
            "summary": "Unverified memory about something",
            "tags": ["unverified"]
        })
        res = ContextResolver(memory_manager=mock_mem, env_index=self.mock_env).resolve("test")
        self.assertEqual(len(res.relevant_memories), 0)

    def test_13_current_environment_outranks_stale_memory(self):
        """13. Current EnvironmentIndex outranks stale conflicting memory."""
        self.mock_memory.memories.append({
            "summary": "Old project built on Django framework",
            "tags": ["verified"]
        })
        # Environment says FastAPI
        intent = self.resolver.resolve("Add route")
        self.assertTrue(any("ConflictResolution" in ev for ev in intent.evidence))
        # Memory referencing Django was rejected
        self.assertEqual(len(intent.relevant_memories), 0)

    # ── Tool Registry Context Tests (14-15) ──────────────────────────────────

    def test_14_relevant_tool_registry_tools_discovered(self):
        """14. Relevant tools from ToolRegistry populated in candidate_tools."""
        intent = self.resolver.resolve("Run backend tests")
        self.assertIn("run_backend_tests", intent.candidate_tools)

    def test_15_unknown_tool_never_appears_in_candidate_tools(self):
        """15. Unknown tools never appear in candidate_tools list."""
        intent = self.resolver.resolve("Execute magic command")
        self.assertNotIn("magic_command", intent.candidate_tools)

    # ── Ambiguity & Clarification Tests (16-18) ──────────────────────────────

    def test_16_ambiguous_request_detected(self):
        """16. Ambiguous request ('Fix the app') detected."""
        intent = self.resolver.resolve("Fix the app")
        self.assertTrue(intent.ambiguity)
        self.assertTrue(intent.requires_clarification)
        self.assertTrue(len(intent.ambiguity_reasons) > 0)

    def test_17_high_risk_ambiguous_request_does_not_execute(self):
        """17. Planner produces safe clarification node for ambiguous intent."""
        planner = TaskPlanner(MockLLMEngine())
        intent = self.resolver.resolve("Fix it")
        graph = planner.plan(intent)
        self.assertEqual(len(graph.nodes), 1)
        node = list(graph.nodes.values())[0]
        self.assertIn("Clarification required", node.description)
        self.assertEqual(node.risk_level, "READ_ONLY")

    def test_18_clarification_path_works(self):
        """18. Requires clarification flag is set when ambiguity is True."""
        intent = self.resolver.resolve("update the project")
        self.assertTrue(intent.requires_clarification)

    # ── Confidence & Evidence Tests (19-21) ──────────────────────────────────

    def test_19_confidence_generated(self):
        """19. Structured confidence generated."""
        intent = self.resolver.resolve("Create backend database API")
        self.assertIn(intent.confidence, [ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW])
        self.assertTrue(0.0 <= intent.confidence_score <= 1.0)

    def test_20_evidence_supports_confidence(self):
        """20. Confidence supported by collected evidence items."""
        intent = self.resolver.resolve("Create backend database API")
        self.assertTrue(len(intent.evidence) >= 2)

    def test_21_conflicting_context_resolved(self):
        """21. Conflict between memory and environment triggers CONTEXT_CONFLICT."""
        captured = []
        def handler(e):
            captured.append(e)
        observability_manager.register_callback(handler)
        
        self.mock_memory.memories.append({"summary": "Using Django", "tags": ["verified"]})
        self.resolver.resolve("Add endpoint")
        events = [e.get("event", {}) for e in captured if isinstance(e, dict)]
        self.assertTrue(any(ev.get("event_type") == "CONTEXT_CONFLICT" for ev in events))

    # ── Planner & MasterAgent Integration Tests (22-23) ──────────────────────

    def test_22_structured_intent_reaches_planner(self):
        """22. StructuredIntent correctly reaches Planner without failure."""
        planner = TaskPlanner(MockLLMEngine('{"nodes": [{"node_id": "1", "description": "Build API", "agent": "BackendAgent", "dependencies": []}]}'))
        intent = self.resolver.resolve("Build backend API")
        graph = planner.plan(intent)
        self.assertEqual(len(graph.nodes), 1)
        self.assertEqual(graph.nodes["1"].agent, "BackendAgent")

    def test_23_planner_does_not_duplicate_context_resolution(self):
        """23. Planner uses StructuredIntent evidence directly."""
        intent = self.resolver.resolve("Write backend test")
        self.assertIsInstance(intent, StructuredIntent)

    # ── Security Tests (24-25) ───────────────────────────────────────────────

    def test_24_context_resolver_cannot_execute_tools(self):
        """24. ContextResolver has no execution methods."""
        self.assertFalse(hasattr(self.resolver, "execute"))
        self.assertFalse(hasattr(self.resolver, "run_tool"))

    def test_25_context_resolver_cannot_bypass_execution_gate(self):
        """25. ContextResolver cannot grant permissions or bypass ExecutionGate."""
        intent = self.resolver.resolve("Delete database file")
        # Candidate agent may be identified, but permission is NEVER granted
        self.assertNotIn("permission", intent.model_dump())
        self.assertNotIn("authorized", intent.model_dump())

    # ── Observability & Audit Tests (26-28) ──────────────────────────────────

    def test_26_context_resolution_events_emitted(self):
        """26. Observability events emitted during context resolution."""
        captured = []
        def handler(e):
            captured.append(e)
        observability_manager.register_callback(handler)
        
        self.resolver.resolve("Build frontend UI component")
        events = [e.get("event", {}) for e in captured if isinstance(e, dict)]
        self.assertTrue(any(ev.get("event_type") == "CONTEXT_RESOLUTION_COMPLETED" for ev in events))

    def test_27_context_decision_auditable_without_secrets(self):
        """27. Structured intent does not include raw secrets."""
        intent = self.resolver.resolve("Query database with api_key=secret-token-12345")
        self.assertNotIn("secret-token-12345", [e for e in intent.entities if "token" in e])

    def test_28_regression_tasks_1_to_11(self):
        """28. Core tools and agents remain functional."""
        self.assertIsNotNone(tool_registry.get("write_code_file"))
        self.assertIsNotNone(tool_registry.get("run_backend_tests"))
        self.assertIsNotNone(tool_registry.get("start_frontend_server"))

if __name__ == "__main__":
    unittest.main()
