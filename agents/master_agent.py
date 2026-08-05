import json
import os
import importlib
import inspect
from typing import Dict

from core.llm_engine import LLMEngine
from core.memory_manager import MemoryManager
from agents.base_agent import BaseAgent
from agents.dev_agent import DevAgent
from agents.academic_agent import AcademicAgent
from agents.system_agent import SystemAgent
from agents.observer_agent import ObserverAgent

class MasterAgent(BaseAgent):
    name = "MasterAgent"
    description = "The central router that analyzes tasks and delegates them to specialized sub-agents."
    
    def __init__(self, llm: LLMEngine, memory: MemoryManager, approval_manager=None):
        super().__init__(llm, memory, approval_manager)
        
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
                try:
                    # Dynamically import the module
                    module = importlib.import_module(f"agents.custom_agents.{module_name}")
                    
                    # Find any class in the module that inherits from BaseAgent
                    for name, obj in inspect.getmembers(module):
                        if inspect.isclass(obj) and issubclass(obj, BaseAgent) and obj is not BaseAgent:
                            if name not in self.agents:
                                print(f"[MasterAgent] Loaded custom agent: {name}")
                                self.agents[name] = obj(self.llm, self.memory, self.approval_manager)
                except Exception as e:
                    print(f"[MasterAgent ERROR] Failed to load custom agent {filename}: {e}")

    def execute(self, task: str) -> str:
        """
        Analyzes the task, chooses the best sub-agent, and delegates execution.
        """
        # If the user specifically asks the observer to run
        if "evolve" in task.lower() or "observe" in task.lower() or "detect gap" in task.lower():
            return self.agents["ObserverAgent"].execute()

        print(f"\n[{self.name}] Analyzing task to determine the best sub-agent...")
        
        # Build a list of available agents and their descriptions
        agent_descriptions = "\n".join([f"- {name}: {agent.description}" for name, agent in self.agents.items() if name != "ObserverAgent"])
        
        prompt = (
            f"You are the Master Routing Agent. Analyze the following user task and select the best sub-agent to handle it.\n"
            f"Available Agents:\n{agent_descriptions}\n\n"
            f"User Task: '{task}'\n\n"
            "Respond ONLY with a JSON object in this format:\n"
            '{"selected_agent": "AgentName", "reasoning": "brief explanation"}'
        )
        
        system_prompt = "You output strict JSON only. No extra text."
        response = self.llm.generate_response(prompt=prompt, system_prompt=system_prompt)
        
        # Parse the JSON response
        try:
            # Strip potential markdown formatting
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
                
            decision = json.loads(response.strip())
            selected_agent_name = decision.get("selected_agent")
            reasoning = decision.get("reasoning")
            
            print(f"[{self.name}] Delegating to {selected_agent_name} because: {reasoning}")
            
            # Delegate task
            if selected_agent_name in self.agents:
                return self.agents[selected_agent_name].execute(task)
            else:
                print(f"[{self.name}] LLM selected unknown agent '{selected_agent_name}'. Falling back to default response.")
                return super().execute(task)
                
        except json.JSONDecodeError:
            print(f"[{self.name} ERROR] Failed to parse routing decision. Falling back to default execution.")
            return super().execute(task)
