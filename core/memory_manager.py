from core.database import ShortTermMemory, LongTermMemory

class MemoryManager:
    """
    Master MemoryManager class that orchestrates both MongoDB (short-term) 
    and ChromaDB (long-term) storage.
    """
    def __init__(self):
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory()

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

        # 2. Store in ChromaDB (Semantic Context for LLM retrieval)
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
