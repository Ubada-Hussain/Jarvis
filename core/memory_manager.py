from core.database import ShortTermMemory, LongTermMemory
import threading
from core.llm_engine import LLMEngine

class MemoryManager:
    """
    Master MemoryManager class that orchestrates both MongoDB (short-term) 
    and ChromaDB (long-term) storage.
    """
    def __init__(self):
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory()

    def _extract_and_save_facts(self, user_input: str, ai_response: str, mongo_id: str):
        """
        Background task to extract facts or preferences from the conversation 
        and save them to ChromaDB.
        """
        try:
            llm = LLMEngine()
            prompt = f"User said: '{user_input}'\nAI replied: '{ai_response}'\n\nExtract any new, distinct user preferences, personal facts, or explicit long-term instructions from the user's statement. If there are none, output exactly 'NONE'. Do not include conversational filler."
            
            fact = llm.generate_response(prompt, system_prompt="You are an information extraction system. You only extract hard facts and preferences. You return 'NONE' if no facts exist.")
            
            if fact and fact.strip().upper() != "NONE":
                metadata = {
                    "type": "extracted_fact",
                    "mongo_id": mongo_id if mongo_id else "unlogged"
                }
                print(f"[MEMORY] Auto-learned fact: {fact.strip()}")
                self.long_term.store_memory(document=fact.strip(), metadata=metadata)
        except Exception as e:
            print(f"[MEMORY ERROR] Auto-learning failed: {e}")

    def save_interaction(self, user_input, ai_response, activity_type="conversation"):
        """
        Orchestrates saving to both MongoDB (logs) and ChromaDB (semantic context).
        
        Args:
            user_input (str): The user's prompt or question.
            ai_response (str): The AI's generated response.
            activity_type (str): Type of interaction for metadata logging.
        """
        # 1. Log to MongoDB (Structured Log for activities and raw history)
        log_data = {
            "type": activity_type,
            "user_input": user_input,
            "ai_response": ai_response
        }
        mongo_id = self.short_term.log_activity("interaction_logs", log_data)

        # 2. Extract facts in the background (Auto-learning)
        threading.Thread(target=self._extract_and_save_facts, args=(user_input, ai_response, mongo_id)).start()

        # 3. Store the raw interaction in ChromaDB (Semantic Context for LLM retrieval)
        # We format the document in a way that helps the LLM understand the context later
        document = f"User asked: {user_input}\nJARVIS responded: {ai_response}"
        metadata = {
            "type": activity_type,
            "mongo_id": mongo_id if mongo_id else "unlogged"
        }
        
        # Link the ChromaDB document ID to the MongoDB object ID for future reference
        self.long_term.store_memory(document=document, metadata=metadata, doc_id=mongo_id)
        
    def get_relevant_context(self, query, max_results=3):
        """
        Retrieves semantically similar past interactions to provide context.
        
        Args:
            query (str): The current user prompt to match against past history.
            max_results (int): Maximum number of historical memories to retrieve.
            
        Returns:
            list: A list of stringified previous interactions.
        """
        return self.long_term.retrieve_context(query, n_results=max_results)
