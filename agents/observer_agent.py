import os
import json
from agents.base_agent import BaseAgent

class ObserverAgent(BaseAgent):
    name = "ObserverAgent"
    description = "Observes interaction logs, identifies repeated patterns, and auto-generates new sub-agents to handle them."

    def execute(self, task: str = None) -> str:
        """
        The Observer Agent doesn't typically take a task directly from the user.
        Instead, it analyzes the database. We can trigger this manually or periodically.
        """
        print(f"\n[{self.name}] Analyzing memory logs for missing agent capabilities...")
        
        # In a real scenario, this would query MemoryManager for recent unhandled tasks.
        # For demonstration, we'll mock a detected gap:
        detected_gap = "The user frequently asks to summarize YouTube videos, but no agent is specialized in video summarization."
        
        print(f"[{self.name}] Detected gap: {detected_gap}")
        
        return self._generate_new_agent(detected_gap)

    def _generate_new_agent(self, gap_description: str) -> str:
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
        # This is simplified. 
        class_name_prompt = f"What is a good PascalCase class name for an agent that does this: {gap_description}? Reply with ONLY the class name."
        class_name = self.llm.generate_response(prompt=class_name_prompt).strip()
        
        # Basic sanitization
        class_name = ''.join(e for e in class_name if e.isalnum())
        file_name = class_name.lower() + ".py"
        
        file_path = os.path.join("agents", "custom_agents", file_name)
        
        try:
            with open(file_path, "w") as f:
                f.write(code)
            
            result = f"Successfully created new agent '{class_name}' at {file_path}"
            print(f"[{self.name}] {result}")
            self.memory.save_interaction(user_input="Auto-generate agent", ai_response=result, activity_type="meta_programming")
            return result
        except Exception as e:
            return f"[{self.name} ERROR] Failed to write new agent to disk: {e}"
