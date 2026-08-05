import os
import subprocess
from duckduckgo_search import DDGS
from agents.base_agent import BaseAgent

class SystemAgent(BaseAgent):
    name = "SystemAgent"
    description = "Specialized in local OS automation (file/folder management, running shell scripts, and web searching using duckduckgo_search)."

    def execute(self, task: str) -> str:
        """
        Custom execution loop to intercept web search or OS tasks.
        """
        print(f"\n[{self.name}] Analyzing system task...")
        
        if "search the web" in task.lower() or "look up" in task.lower():
            return self._search_web(task)
            
        # Fallback to LLM if it's a general OS question
        return super().execute(task)

    def _search_web(self, query: str) -> str:
        """Uses duckduckgo_search to fetch information from the web."""
        try:
            print(f"[{self.name}] Searching web for: {query}")
            results = DDGS().text(query, max_results=3)
            
            if not results:
                return "No results found on the web."
                
            formatted_results = "\n\n".join([f"Title: {r['title']}\nBody: {r['body']}\nURL: {r['href']}" for r in results])
            
            # Feed the results back to the LLM to summarize
            prompt = f"Summarize these search results for the user's query '{query}':\n\n{formatted_results}"
            summary = super().execute(prompt)
            return summary
            
        except Exception as e:
            return f"[{self.name} ERROR] Web search failed: {e}"
