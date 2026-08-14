import json
import uuid
from enum import Enum
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field, asdict

class TaskState(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING_FOR_DEPENDENCY = "WAITING_FOR_DEPENDENCY"
    WAITING_FOR_CONFIRMATION = "WAITING_FOR_CONFIRMATION"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
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
    """
    def __init__(self, llm_engine):
        self.llm = llm_engine

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
        Creates a Task Graph by consulting the LLM.
        """
        graph_id = f"graph-{uuid.uuid4()}"
        
        agent_descriptions = "\n".join([f"- {name}: {desc}" for name, desc in available_agents.items()])
        
        prompt = (
            f"You are the JARVIS Task Planner. Break down the user objective into a Task Graph with dependencies.\n"
            f"Objective: '{objective}'\n\n"
            f"Available Agents:\n{agent_descriptions}\n\n"
            "RULES:\n"
            "1. You MUST ONLY assign tasks to the Available Agents listed above. If an agent does not exist for a subtask, assign it to 'NOT_AVAILABLE'.\n"
            "2. Complex tasks should be broken into sequential or parallel steps.\n"
            "3. If tasks can be executed simultaneously without conflicting (e.g., read-only lookups), leave their 'dependencies' list empty.\n"
            "4. If a task requires the output of another task, list the preceding task's node_id in the 'dependencies' array.\n"
            "5. NO CYCLIC DEPENDENCIES. (A depends on B, B depends on A).\n"
            "6. Be conservative with parallel execution. If unsure, make them sequential.\n\n"
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
