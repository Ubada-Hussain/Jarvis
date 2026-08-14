import os
import json
from agents.base_agent import BaseAgent

class ObserverAgent(BaseAgent):
    name = "ObserverAgent"
    description = "Observes interaction logs, identifies repeated patterns, and auto-generates new sub-agents to handle them."

    def execute(self, task: str = None, task_id: str = None) -> str:
        """
        The Observer Agent doesn't typically take a task directly from the user.
        Instead, it analyzes the database. We can trigger this manually or periodically.
        """
        print(f"\n[{self.name}] Analyzing memory logs for missing agent capabilities...")
        
        # In a real scenario, this would query MemoryManager for recent unhandled tasks.
        # For demonstration, we'll mock a detected gap:
        detected_gap = "The user frequently asks to summarize YouTube videos, but no agent is specialized in video summarization."
        
        print(f"[{self.name}] Detected gap: {detected_gap}")
        
        return self._generate_new_agent(detected_gap, task_id)

    def _generate_new_agent(self, gap_description: str, task_id: str = None) -> str:
        """
        Generates Python code for a new agent and writes it to custom_agents directory.
        """
        prompt = (
            f"We need a new Python agent class to handle this capability: {gap_description}\n"
            "Requirements:\n"
            "1. Inherit from 'BaseAgent' (from agents.base_agent import BaseAgent)\n"
            "2. Define 'name' and 'description' class variables.\n"
            "3. Optionally override the 'execute' method.\n"
            "Output ONLY valid Python code. No markdown formatting, no explanations."
        )
        
        system_prompt = "You are a master Python meta-programmer. Output only raw python code."
        gate = self._setup_execution_gate(task_id)
        code = self.llm.generate_response(prompt=prompt, system_prompt=system_prompt)
        
        if not code:
            return f"[{self.name} ERROR] Failed to generate agent code."
            
        # Clean up possible markdown code blocks if the LLM adds them despite instructions
        if code.startswith("```python"):
            code = code[9:]
        if code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]
            
        code = code.strip()

        # Generate a filename (e.g., VideoAgent -> video_agent.py)
        class_name_prompt = f"What is a good PascalCase class name for an agent that does this: {gap_description}? Reply with ONLY the class name."
        class_name = self.llm.generate_response(prompt=class_name_prompt).strip()
        
        # Basic sanitization
        class_name = ''.join(e for e in class_name if e.isalnum())
        file_name = class_name.lower() + ".py"
        
        pending_dir = os.path.join("agents", "pending")
        os.makedirs(pending_dir, exist_ok=True)
        file_path = os.path.join(pending_dir, file_name)
        
        try:
            with open(file_path, "w") as f:
                f.write(code)
            
            result = f"Successfully drafted new agent '{class_name}' at {file_path}. Pending user approval."
            print(f"[{self.name}] {result}")
            
            # Request approval from the user via the frontend popup
            if self.approval_manager:
                action_desc = f"Install new Meta-Agent: {class_name}\n\nCode Preview:\n```python\n{code[:300]}...\n```"
                approved = self.approval_manager.request_approval(action_desc)
                if approved:
                    # Move to custom_agents
                    final_dir = os.path.join("agents", "custom_agents")
                    os.makedirs(final_dir, exist_ok=True)
                    final_path = os.path.join(final_dir, file_name)
                    os.replace(file_path, final_path)
                    
                    # Log to memory
                    self.memory.save_interaction(user_input="Auto-generate agent", ai_response=f"Installed {class_name}", activity_type="meta_programming")
                    return f"[{self.name}] Agent {class_name} approved and installed to {final_path}."
                else:
                    return f"[{self.name}] Installation of {class_name} was rejected by user."
            else:
                return f"[{self.name}] No approval manager found. Agent code kept in pending state: {file_path}."
        except Exception as e:
            return f"[{self.name} ERROR] Failed to write new agent to disk: {e}"
