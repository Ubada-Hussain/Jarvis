from agents.base_agent import BaseAgent

class AcademicAgent(BaseAgent):
    name = "AcademicAgent"
    description = "Specialized in academic research, summarizing topics, drafting structured project outlines, and database schema design."

    def execute(self, task: str) -> str:
        """
        Executes a task focused on academic structure and research.
        """
        print(f"\n[{self.name}] Researching and structuring...")
        
        # We augment the system prompt to enforce a structured academic tone
        system_prompt = (
            f"You are {self.name}. {self.description}\n"
            "Format your responses with clear headings, bullet points, and an objective tone. "
            "If asked for a schema, provide it in a structured format (like JSON or Markdown tables)."
        )
        
        response = self.llm.generate_response(prompt=task, system_prompt=system_prompt)
        
        if not response:
            return f"[{self.name} ERROR]: Failed to generate response."

        self.memory.save_interaction(
            user_input=task, 
            ai_response=response, 
            activity_type=f"agent_execution_{self.name}"
        )
        return response
