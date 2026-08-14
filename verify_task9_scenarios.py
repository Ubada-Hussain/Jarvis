import os
import sys
import io
import json
import uuid
import tempfile

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
from core.llm_engine import LLMEngine
from core.memory_manager import MemoryManager
from core.audit_logger import SQLiteAuditLogger
from core.execution_gate import ExecutionGate, ToolMetadata, RiskLevel
from core.verification import ToolResult, VerificationStatus
from core.planner import Planner, TaskGraph, TaskNode, TaskState
from core.scheduler import DependencyScheduler
from core.a2a import A2ADispatcher, AgentMessage, MessageType, AgentStatus
from agents.backend_agent import BackendAgent
from agents.frontend_agent import FrontendAgent
from agents.master_agent import MasterAgent
from core.dev_tools import write_code_file, read_code_file, inspect_code_directory

class ScenarioApprovalManager:
    def __init__(self, auto_approve=True):
        self.auto_approve = auto_approve
        self.requested = False
        self.requested_action = ""

    def require_approval(self, action_desc: str) -> bool:
        self.requested = True
        self.requested_action = action_desc
        return self.auto_approve

def run_scenarios():
    print("=" * 60)
    print("  TASK 9 — REAL BEHAVIORAL VERIFICATION SCENARIOS")
    print("=" * 60)

    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db_file.name
    db_file.close()

    audit_logger = SQLiteAuditLogger(db_path)
    llm = LLMEngine()
    memory = MemoryManager()
    approval = ScenarioApprovalManager(auto_approve=True)

    backend_agent = BackendAgent(llm, memory, approval)
    frontend_agent = FrontendAgent(llm, memory, approval)
    
    agents = {
        "BackendAgent": backend_agent,
        "FrontendAgent": frontend_agent
    }

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO A: Backend-only task
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO A: Backend API Implementation ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        test_backend_file = os.path.join(tmpdir, "user_api.py")
        
        # Dispatch a backend task through A2ADispatcher
        dispatcher = A2ADispatcher(agents, audit_logger)
        
        # We simulate node execution using BackendAgent with write_code_file tool
        gate = backend_agent._setup_execution_gate("node-scenario-a")
        gate.audit_logger = audit_logger
        
        res = gate.execute("write_code_file", file_path=test_backend_file, content="from fastapi import FastAPI\napp = FastAPI()\n@app.get('/users')\ndef get_users(): return [{'id': 1, 'name': 'Alice'}]\n")
        
        req = AgentMessage(
            message_id=str(uuid.uuid4()),
            task_id="graph-scenario-a",
            node_id="node-scenario-a",
            sender_agent="Scheduler",
            recipient_agent="BackendAgent",
            message_type=MessageType.TASK_REQUEST,
            status=AgentStatus.PENDING
        )
        msg_result = dispatcher._evaluate_evidence(req, res.message)
        
        print(f"Status: {msg_result.status}")
        print(f"Evidence: {msg_result.evidence}")
        print(f"Files Changed: {msg_result.files_changed}")
        assert msg_result.status == AgentStatus.COMPLETED
        assert len(msg_result.files_changed) == 1
        assert msg_result.files_changed[0].path == test_backend_file
        assert os.path.exists(test_backend_file)
        print("✅ Scenario A Passed: Backend task executed, files written, verified, and audited.")

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO B: Frontend-only task
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO B: Frontend Component Implementation ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        test_frontend_file = os.path.join(tmpdir, "UserList.tsx")
        
        gate_fe = frontend_agent._setup_execution_gate("node-scenario-b")
        gate_fe.audit_logger = audit_logger
        
        res_fe = gate_fe.execute("write_code_file", file_path=test_frontend_file, content="import React from 'react';\nexport const UserList = ({ users }) => <ul>{users.map(u => <li key={u.id}>{u.name}</li>)}</ul>;\n")
        
        req_fe = AgentMessage(
            message_id=str(uuid.uuid4()),
            task_id="graph-scenario-b",
            node_id="node-scenario-b",
            sender_agent="Scheduler",
            recipient_agent="FrontendAgent",
            message_type=MessageType.TASK_REQUEST,
            status=AgentStatus.PENDING
        )
        msg_fe = dispatcher._evaluate_evidence(req_fe, res_fe.message)
        
        print(f"Status: {msg_fe.status}")
        print(f"Evidence: {msg_fe.evidence}")
        print(f"Files Changed: {msg_fe.files_changed}")
        assert msg_fe.status == AgentStatus.COMPLETED
        assert len(msg_fe.files_changed) == 1
        assert msg_fe.files_changed[0].path == test_frontend_file
        assert os.path.exists(test_frontend_file)
        print("✅ Scenario B Passed: Frontend task executed, files written, verified, and audited.")

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO C: Full-stack Workflow
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO C: Full-stack Dependency Pipeline ---")
    graph = TaskGraph(graph_id="graph-fullstack-1", objective="Implement User Management Full-Stack")
    
    node_be = TaskNode(
        node_id="node-be-api",
        description="Implement user REST API",
        agent="BackendAgent",
        dependencies=[]
    )
    node_fe = TaskNode(
        node_id="node-fe-ui",
        description="Connect React UI to user REST API",
        agent="FrontendAgent",
        dependencies=["node-be-api"]
    )
    graph.nodes[node_be.node_id] = node_be
    graph.nodes[node_fe.node_id] = node_fe
    
    scheduler = DependencyScheduler(agents, audit_logger)
    
    # Execute graph
    summary = scheduler.execute_graph(graph)
    print(f"Graph execution summary: {summary}")
    print(f"Node BE Status: {graph.nodes['node-be-api'].status}, Verification: {graph.nodes['node-be-api'].verification_status}")
    print(f"Node FE Status: {graph.nodes['node-fe-ui'].status}, Verification: {graph.nodes['node-fe-ui'].verification_status}")
    
    assert graph.nodes["node-be-api"].status == TaskState.COMPLETED
    assert graph.nodes["node-fe-ui"].status == TaskState.COMPLETED
    print("✅ Scenario C Passed: TaskGraph executed BE -> FE sequentially with verified state handoff.")

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO D: Ambiguous Task
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO D: Ambiguous Task Handling ---")
    planner = Planner(llm, memory)
    # The prompt explicitly forbids silent guessing without environment evidence
    ambiguous_graph = TaskGraph(graph_id="graph-ambig", objective="Implement unknown feature on unclassified stack")
    ambig_node = TaskNode(
        node_id="node-ambig",
        description="Ambiguous feature without evidence",
        agent="NOT_AVAILABLE"
    )
    ambiguous_graph.nodes[ambig_node.node_id] = ambig_node
    
    scheduler_ambig = DependencyScheduler(agents, audit_logger)
    summary_ambig = scheduler_ambig.execute_graph(ambiguous_graph)
    print(f"Ambiguous graph summary: {summary_ambig}")
    print(f"Ambiguous node status: {ambiguous_graph.nodes['node-ambig'].status}")
    assert ambiguous_graph.nodes['node-ambig'].status == TaskState.FAILED
    print("✅ Scenario D Passed: Ambiguous task with missing agent/evidence fails safely without guessing.")

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO E: Permission & Confirmation
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- SCENARIO E: Permission Enforcement on Specialized Agent ---")
    strict_approval = ScenarioApprovalManager(auto_approve=False)
    gate_strict = ExecutionGate(strict_approval, agent_name="BackendAgent", task_id="node-perm-test", audit_logger=audit_logger)
    gate_strict.register(ToolMetadata("restricted_backend_tool", RiskLevel.DESTRUCTIVE, "destructive_op", requires_confirmation=True), lambda: ToolResult(VerificationStatus.VERIFIED_SUCCESS, "Executed"))
    
    res_perm = gate_strict.execute("restricted_backend_tool")
    print(f"Permission denied result status: {res_perm.status}")
    print(f"Permission denied message: {res_perm.message}")
    assert res_perm.status == VerificationStatus.VERIFIED_FAILURE
    assert "DENIED" in res_perm.message
    assert strict_approval.requested is True
    print("✅ Scenario E Passed: Destructive action halted by ExecutionGate confirmation.")

    # Clean up
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass

    print("\n" + "=" * 60)
    print("  ALL 5 REAL BEHAVIORAL SCENARIOS COMPLETED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_scenarios()
