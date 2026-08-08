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
        
        # Thread pool for parallel agent execution
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="agent")
        
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

    def _run_agent(self, agent_name: str, task: str) -> Tuple[str, str]:
        """
        Execute a single agent's task. This runs INSIDE a thread pool thread.
        Updates agent status before/after execution.
        """
        _update_agent_status(agent_name, "working")
        try:
            result = self.agents[agent_name].execute(task)
            return (agent_name, result)
        except Exception as e:
            return (agent_name, f"[{agent_name} ERROR] {str(e)}")
        finally:
            _update_agent_status(agent_name, "idle")

    def execute(self, task: str) -> str:
        """
        Analyzes the task, chooses the best sub-agent(s), and delegates execution.
        Supports PARALLEL dispatch when multiple agents are needed.
        MasterAgent does NOT execute any task itself — only routes and explains.
        """
        # Hot-load any new agents installed by the Observer before routing
        self._load_custom_agents()
        
        # If the user specifically asks the observer to run
        if "evolve" in task.lower() or "observe" in task.lower() or "detect gap" in task.lower():
            _update_agent_status("ObserverAgent", "working")
            try:
                return self.agents["ObserverAgent"].execute()
            finally:
                _update_agent_status("ObserverAgent", "idle")

        print(f"\n[{self.name}] Analyzing task to determine the best sub-agent(s)...")
        
        # Build a list of available agents and their descriptions
        agent_descriptions = "\n".join([
            f"- {name}: {agent.description}" 
            for name, agent in self.agents.items() 
            if name != "ObserverAgent"
        ])
        
        prompt = (
            f"You are the Master Routing Agent. Analyze the following user task and decide which sub-agent(s) should handle it.\n"
            f"Available Agents:\n{agent_descriptions}\n\n"
            f"User Task: '{task}'\n\n"
            "RULES:\n"
            "1. If the task clearly belongs to ONE agent's domain, assign it to that single agent.\n"
            "2. If the task contains MULTIPLE independent sub-tasks that belong to DIFFERENT agents, split them and assign each sub-task to the appropriate agent.\n"
            "3. For simple greetings or general questions that don't need any agent's tools, use the agent whose domain is closest.\n\n"
            "Respond ONLY with a JSON object in this format:\n"
            '{"assignments": [{"agent": "AgentName", "task": "the specific sub-task for this agent"}], "reasoning": "brief explanation"}\n'
            "IMPORTANT: The 'assignments' array can have 1 or more entries. Each entry must have 'agent' and 'task' keys."
        )
        
        system_prompt = "You output strict JSON only. No extra text."
        response = self.llm.generate_response(prompt=prompt, system_prompt=system_prompt)
        
        # Parse the JSON response
        try:
            # Strip potential markdown formatting
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
                
            decision = json.loads(response.strip())
            assignments = decision.get("assignments", [])
            reasoning = decision.get("reasoning", "")
            
            # Fallback: support old single-agent format
            if not assignments and "selected_agent" in decision:
                assignments = [{"agent": decision["selected_agent"], "task": task}]
            
            if not assignments:
                print(f"[{self.name}] No assignments parsed. Falling back.")
                return super().execute(task)
            
            print(f"[{self.name}] Routing decision: {reasoning}")
            for a in assignments:
                print(f"  → {a['agent']}: {a['task'][:80]}...")
            
            # ── PARALLEL DISPATCH ──────────────────────────────────────────────
            if len(assignments) == 1:
                # Single agent — run directly (no thread overhead)
                agent_name = assignments[0]["agent"]
                agent_task = assignments[0]["task"]
                if agent_name in self.agents:
                    _update_agent_status(agent_name, "working")
                    try:
                        result = self.agents[agent_name].execute(agent_task)
                    finally:
                        _update_agent_status(agent_name, "idle")
                    return result
                else:
                    print(f"[{self.name}] Unknown agent '{agent_name}'. Falling back.")
                    return super().execute(task)
            else:
                # MULTIPLE agents — run in PARALLEL
                print(f"\n[{self.name}] Dispatching {len(assignments)} agents in PARALLEL...")
                futures: List[Tuple[str, Future]] = []
                
                for assignment in assignments:
                    agent_name = assignment["agent"]
                    agent_task = assignment["task"]
                    if agent_name in self.agents:
                        future = self._executor.submit(self._run_agent, agent_name, agent_task)
                        futures.append((agent_name, future))
                    else:
                        print(f"[{self.name}] Skipping unknown agent '{agent_name}'.")
                
                # Collect all results
                results = []
                for agent_name, future in futures:
                    try:
                        name, result = future.result(timeout=60)
                        results.append((name, result))
                    except Exception as e:
                        results.append((agent_name, f"[ERROR] {str(e)}"))
                
                # Synthesize a combined response using LLM
                return self._synthesize_results(task, results)
                
        except json.JSONDecodeError:
            print(f"[{self.name} ERROR] Failed to parse routing decision. Falling back.")
            return super().execute(task)

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
            system_prompt="You are JARVIS. Summarize the parallel agent results naturally."
        )
