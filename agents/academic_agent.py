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
            "You can converse naturally in English, Urdu, and Punjabi, but YOU MUST DEFAULT TO ENGLISH. "
            "CRITICAL RULE: If the user types in English (e.g., 'Hello', 'Hi'), YOU MUST REPLY IN ENGLISH. ONLY use Urdu or Punjabi if the user explicitly writes in those languages (e.g., 'kya haal hai', 'کیا حال ہے'). "
            "CRITICAL RULE: DO NOT use any tools for simple greetings or casual chit-chat. Only use tools when explicitly asked to perform an action. "
            "Provide deeply researched, educational, and cited responses. "
            "Format your responses with clear headings, bullet points, and an objective tone. "
            "If asked for a schema, provide it in a structured format (like JSON or Markdown tables)."
        )
        
        # --- RAG / Memory Injection ---
        try:
            relevant_chunks = self.memory.get_relevant_context(task, max_results=3)
            if relevant_chunks:
                system_prompt += "\n\n<MEMORY_CONTEXT>\n"
                for chunk in relevant_chunks:
                    system_prompt += f"- {chunk}\n"
                system_prompt += "</MEMORY_CONTEXT>\n"
        except Exception as e:
            print(f"[RAG WARNING] Failed to retrieve context: {e}")

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
