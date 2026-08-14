import json
import uuid
from enum import Enum
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field, asdict
import os
from core.environment_index import EnvironmentIndex

class TaskState(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    RETRYING = "RETRYING"
    RECOVERING = "RECOVERING"
    WAITING_FOR_DEPENDENCY = "WAITING_FOR_DEPENDENCY"
    WAITING_FOR_CONFIRMATION = "WAITING_FOR_CONFIRMATION"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    ESCALATED = "ESCALATED"
    SKIPPED = "SKIPPED"

@dataclass
class TaskNode:
    node_id: str
    description: str
    agent: str
    dependencies: List[str] = field(default_factory=list)
    required_capabilities: List[str] = field(default_factory=list)
    risk_level: str = "UNKNOWN"
    status: TaskState = TaskState.PENDING
    result: str = ""
    error: str = ""
    verification_status: str = "UNVERIFIED"
    attempts: int = 0
    max_retries: int = 2
    failure_category: Optional[str] = None

@dataclass
class TaskGraph:
    graph_id: str
    objective: str
    nodes: Dict[str, TaskNode] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "graph_id": self.graph_id,
            "objective": self.objective,
            "nodes": {k: asdict(v) for k, v in self.nodes.items()}
        }

class Planner:
    """
    Translates user objectives into a dependency-aware Task Graph.
    Uses LLM to break down tasks securely and assign to existing agents.
    Can also instantiate pre-verified TaskGraphs from ProceduralMemory.
    """
    def __init__(self, llm_engine, memory_manager=None):
        self.llm = llm_engine
        self.memory = memory_manager
        self.env_index = EnvironmentIndex()

    def _parse_llm_json(self, response: str) -> dict:
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        elif response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        return json.loads(response.strip())

    def create_graph(self, objective: str, available_agents: Dict[str, str]) -> TaskGraph:
        """
        Creates a Task Graph. First checks for ProceduralMemory matches,
        falling back to LLM generation if none exist.
        """
        graph_id = f"graph-{uuid.uuid4()}"
        
        # 1. Check for Procedural Memory matches
        if self.memory:
            results = self.memory.get_relevant_context(objective, memory_types=["procedural"], max_results=1)
            if results:
                match = results[0]["data"]
                # Create graph from procedure
                graph = TaskGraph(graph_id=graph_id, objective=objective)
                prev_node_id = None
                for i, step_dict in enumerate(match.get("steps", [])):
                    node_id = f"{match.get('procedure_id')}-step-{i}"
                    
                    # For simplicity, default sequential execution
                    deps = [prev_node_id] if prev_node_id else []
                    
                    node = TaskNode(
                        node_id=node_id,
                        description=f"{step_dict.get('action')}: {step_dict.get('description')}",
                        agent=step_dict.get("agent", "SystemAgent"),
                        dependencies=deps,
                        risk_level="UNKNOWN"
                    )
                    graph.nodes[node_id] = node
                    prev_node_id = node_id
                    
                print(f"[Planner] Used Procedural Memory '{match.get('name')}' to generate graph.")
                return graph
        
        # 2. Fallback to LLM Planning
        agent_descriptions = "\n".join([f"- {name}: {desc}" for name, desc in available_agents.items()])
        
        env_context = ""
        project_root = os.getcwd()
        env_knowledge = self.env_index.get_knowledge(project_root)
        if env_knowledge:
            languages = ", ".join([f.value for f in env_knowledge.languages])
            frameworks = ", ".join([f.value for f in env_knowledge.frameworks])
            entry_points = ", ".join([f.value for f in env_knowledge.entry_points])
            env_context = (
                f"\nENVIRONMENT CONTEXT (Project: {project_root}):\n"
                f"- Languages: {languages or 'Unknown'}\n"
                f"- Frameworks: {frameworks or 'Unknown'}\n"
                f"- Entry Points: {entry_points or 'Unknown'}\n"
            )
        
        prompt = (
            f"You are the JARVIS Task Planner. Break down the user objective into a Task Graph with dependencies.\n"
            f"Objective: '{objective}'\n\n"
            f"Available Agents:\n{agent_descriptions}\n{env_context}\n"
            "RULES:\n"
            "1. You MUST ONLY assign tasks to the Available Agents listed above. If an agent does not exist for a subtask, assign it to 'NOT_AVAILABLE'.\n"
            "2. CAPABILITY ROUTING:\n"
            "   - Assign backend tasks (APIs, server services, database, backend tests, python logic) to 'BackendAgent'.\n"
            "   - Assign frontend tasks (UI components, styling, Vite dev server, frontend state, React) to 'FrontendAgent'.\n"
            "   - For full-stack/mixed objectives, create distinct subtasks for BackendAgent and FrontendAgent with appropriate dependency ordering (e.g. Frontend depends on Backend API).\n"
            "   - If task domain is AMBIGUOUS and Environment Index lacks evidence, do NOT silently guess: assign to 'NOT_AVAILABLE' or safe inspection.\n"
            "3. Complex tasks should be broken into sequential or parallel steps.\n"
            "4. If tasks can be executed simultaneously without conflicting (e.g., read-only lookups), leave their 'dependencies' list empty.\n"
            "5. If a task requires the output of another task, list the preceding task's node_id in the 'dependencies' array.\n"
            "6. NO CYCLIC DEPENDENCIES. (A depends on B, B depends on A).\n"
            "7. Be conservative with parallel execution. If unsure, make them sequential.\n\n"
            "Respond ONLY with a JSON object in this exact format:\n"
            "{\n"
            '  "nodes": [\n'
            '    {\n'
            '       "node_id": "unique_string_id",\n'
            '       "description": "Clear actionable instruction",\n'
            '       "agent": "AgentName",\n'
            '       "dependencies": ["other_node_id"],\n'
            '       "risk_level": "READ_ONLY | REVERSIBLE | EXTERNAL_SIDE_EFFECT | DESTRUCTIVE"\n'
            '    }\n'
            "  ]\n"
            "}\n"
        )
        
        response_str = self.llm.generate_response(
            prompt=prompt,
            system_prompt="You output strict JSON only. No markdown, no extra text."
        )
        
        try:
            plan = self._parse_llm_json(response_str)
            graph = TaskGraph(graph_id=graph_id, objective=objective)
            
            for node_data in plan.get("nodes", []):
                # Ensure agent is valid
                agent = node_data.get("agent")
                if agent not in available_agents and agent != "NOT_AVAILABLE":
                    agent = "NOT_AVAILABLE"
                    
                node = TaskNode(
                    node_id=node_data.get("node_id", str(uuid.uuid4())),
                    description=node_data.get("description", ""),
                    agent=agent,
                    dependencies=node_data.get("dependencies", []),
                    risk_level=node_data.get("risk_level", "UNKNOWN")
                )
                graph.nodes[node.node_id] = node
                
            self._validate_no_cycles(graph)
            return graph
            
        except Exception as e:
            # Fallback to a single-node graph using SystemAgent if JSON fails
            print(f"[Planner ERROR] Failed to parse graph: {e}")
            graph = TaskGraph(graph_id=graph_id, objective=objective)
            fallback_node = TaskNode(
                node_id="task-0",
                description=objective,
                agent="SystemAgent" if "SystemAgent" in available_agents else "NOT_AVAILABLE"
            )
            graph.nodes[fallback_node.node_id] = fallback_node
            return graph

    def _validate_no_cycles(self, graph: TaskGraph):
        """Raises exception if cyclic dependency exists."""
        visited = set()
        path = set()
        
        def visit(node_id):
            if node_id in path:
                raise ValueError(f"Cyclic dependency detected involving node {node_id}")
            if node_id in visited:
                return
                
            path.add(node_id)
            node = graph.nodes.get(node_id)
            if node:
                for dep in node.dependencies:
                    visit(dep)
            path.remove(node_id)
            visited.add(node_id)
            
        for node_id in graph.nodes:
            visit(node_id)
