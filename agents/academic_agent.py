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
            "You can converse naturally in English, Urdu, and Punjabi. "
            "CRITICAL RULE: Always reply in the same language the user speaks to you (e.g., if they speak Urdu, reply in Urdu using the native script like 'کیا حال ہے'). "
            "Provide deeply researched, educational, and cited responses. "
            "Format your responses with clear headings, bullet points, and an objective tone. "
            "If asked for a schema, provide it in a structured format (like JSON or Markdown tables)."
        )
        
        from core.tools import SEARCH_INTERNET_TOOL, search_internet
        
        response = self.llm.generate_response(
            prompt=task, 
            system_prompt=system_prompt,
            tools=[SEARCH_INTERNET_TOOL],
            tool_logic={"search_internet": search_internet}
        )
        
        if not response:
            return f"[{self.name} ERROR]: Failed to generate response."

        self.memory.save_interaction(
            user_input=task, 
            ai_response=response, 
            activity_type=f"agent_execution_{self.name}"
        )
        return response
