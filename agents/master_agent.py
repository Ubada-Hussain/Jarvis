import json
import os
import importlib
import inspect
import time
from typing import Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor, Future

from core.llm_engine import LLMEngine
from core.memory_manager import MemoryManager
from agents.base_agent import BaseAgent
from agents.dev_agent import DevAgent
from agents.academic_agent import AcademicAgent
from agents.system_agent import SystemAgent
from agents.observer_agent import ObserverAgent
from core.observability import observability_manager
from core.planner import Planner
from core.scheduler import DependencyScheduler
from core.audit_logger import SQLiteAuditLogger
import uuid


# ─── Global agent status tracker ──────────────────────────────────────────────
# This dict is read by the WS endpoint in api_server.py to push live updates.
agent_status: Dict[str, str] = {
    "DEV": "idle",
    "SYS": "idle",
    "ACAD": "idle",
    "OBS": "idle",
}

# Mapping from class names to short display IDs
_AGENT_ID_MAP = {
    "DevAgent": "DEV",
    "SystemAgent": "SYS",
    "AcademicAgent": "ACAD",
    "ObserverAgent": "OBS",
}

# Callback set by api_server.py to push agent status changes over WS
_on_agent_status_change = None

def set_agent_status_callback(cb):
    global _on_agent_status_change
    _on_agent_status_change = cb

def _update_agent_status(agent_name: str, status: str):
    short_id = _AGENT_ID_MAP.get(agent_name, agent_name)
    agent_status[short_id] = status
    if _on_agent_status_change:
        try:
            _on_agent_status_change(agent_status.copy())
        except Exception:
            pass


class MasterAgent(BaseAgent):
    name = "MasterAgent"
    description = "The central router that analyzes tasks and delegates them to specialized sub-agents. It NEVER executes tasks itself — it only routes, monitors, and explains results."
    
    def __init__(self, llm: LLMEngine, memory: MemoryManager, approval_manager=None):
        super().__init__(llm, memory, approval_manager)
        
        # Thread pool is now managed by Scheduler
        self.audit_logger = SQLiteAuditLogger()
        self.planner = Planner(self.llm)
        
        # Initialize standard agents
        self.agents: Dict[str, BaseAgent] = {
            "DevAgent": DevAgent(llm, memory, approval_manager),
            "AcademicAgent": AcademicAgent(llm, memory, approval_manager),
            "SystemAgent": SystemAgent(llm, memory, approval_manager),
            "ObserverAgent": ObserverAgent(llm, memory, approval_manager)
        }
        
        # Load dynamically generated agents
        self._load_custom_agents()

    def _load_custom_agents(self):
        """Dynamically imports and registers agents from the custom_agents folder."""
        custom_agents_dir = os.path.join("agents", "custom_agents")
        if not os.path.exists(custom_agents_dir):
            return
            
        for filename in os.listdir(custom_agents_dir):
            if filename.endswith(".py") and filename != "__init__.py":
                module_name = filename[:-3]
                full_module_name = f"agents.custom_agents.{module_name}"
                try:
                    import sys
                    if full_module_name in sys.modules:
                        module = importlib.reload(sys.modules[full_module_name])
                    else:
                        module = importlib.import_module(full_module_name)
                    
                    for name, obj in inspect.getmembers(module):
                        if inspect.isclass(obj) and issubclass(obj, BaseAgent) and obj is not BaseAgent:
                            if name not in self.agents:
                                print(f"[MasterAgent] Loaded custom agent: {name}")
                                self.agents[name] = obj(self.llm, self.memory, self.approval_manager)
                except Exception as e:
                    print(f"[MasterAgent ERROR] Failed to load custom agent {filename}: {e}")

        pass # Moved to DependencyScheduler

    def execute(self, task: str) -> str:
        """
        Analyzes the task, chooses the best sub-agent(s), and delegates execution.
        Supports PARALLEL dispatch when multiple agents are needed.
        MasterAgent does NOT execute any task itself — only routes and explains.
        """
        task_id = str(uuid.uuid4())
        observability_manager.start_task(task_id, task)
        
        try:
            # Hot-load any new agents installed by the Observer before routing
            self._load_custom_agents()
        
        # If the user specifically asks the observer to run
        if "evolve" in task.lower() or "observe" in task.lower() or "detect gap" in task.lower():
            _update_agent_status("ObserverAgent", "working")
            observability_manager.update_agent("ObserverAgent")
            try:
                result = self.agents["ObserverAgent"].execute()
                observability_manager.end_task(status="COMPLETED")
                return result
            except Exception as e:
                observability_manager.end_task(status="FAILED", error=str(e))
                raise
            finally:
                _update_agent_status("ObserverAgent", "idle")

        print(f"\n[{self.name}] Analyzing task to generate a Task Graph with dependencies...")
        
        # Build available agents dict
        available_agents = {name: agent.description for name, agent in self.agents.items() if name != "ObserverAgent"}
        
        try:
            graph = self.planner.create_graph(task, available_agents)
            
            print(f"[{self.name}] Task Graph created with {len(graph.nodes)} nodes.")
            for node_id, node in graph.nodes.items():
                print(f"  → {node.agent}: {node.description[:60]}... (Deps: {node.dependencies})")
                
            scheduler = DependencyScheduler(self.agents, self.audit_logger)
            
            # Start execution of the graph
            result_summary = scheduler.execute_graph(graph)
            
            # Synthesize final response
            observability_manager.update_agent("MasterAgent")
            
            # Collect results for synthesis
            results = [(n.agent, n.result or f"Failed/Blocked: {n.error}") for n in graph.nodes.values()]
            
            result = self._synthesize_results(task, results)
            observability_manager.end_task(status="COMPLETED")
            return result
            
        except Exception as e:
            print(f"[{self.name} ERROR] Task Graph execution failed: {e}")
            observability_manager.end_task(status="FAILED", error=str(e))
            raise

    def _synthesize_results(self, original_task: str, results: List[Tuple[str, str]]) -> str:
        """
        Takes results from multiple parallel agents and produces a single
        coherent response for the user. MasterAgent explains what each agent did.
        """
        results_text = "\n\n".join([
            f"--- {name} Result ---\n{result}" for name, result in results
        ])
        
        prompt = (
            f"You are JARVIS, an AI assistant. Multiple sub-agents have completed their tasks in parallel.\n"
            f"Original user request: '{original_task}'\n\n"
            f"Results from agents:\n{results_text}\n\n"
            "Synthesize these results into ONE clear, natural response for the user. "
            "Address each completed task. Be concise but informative. "
            "Speak as JARVIS — confident, professional, and helpful."
        )
        
        return self.llm.generate_response(
            prompt=prompt,
            system_prompt="You are JARVIS. Keep responses brief, crisp, confident, and slightly witty (Iron Man style). 1-3 sentences typically. Avoid formal, corporate AI language."
        )
