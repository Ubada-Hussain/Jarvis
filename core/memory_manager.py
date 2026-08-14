from core.database import ShortTermMemory, LongTermMemory, StructuredMemoryStore
from core.memory_models import EpisodicMemory, ProceduralMemory, MemoryType, MemoryQuery
import threading
from core.llm_engine import LLMEngine
from core.observability import observability_manager, ObservabilityEvent

class MemoryManager:
    """
    Master MemoryManager class that orchestrates both MongoDB (short-term) 
    and ChromaDB (long-term) storage.
    """
    def __init__(self):
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory()
        self.structured = StructuredMemoryStore()

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
        
    def get_relevant_context(self, query: str, memory_types: list = None, max_results: int = 3):
        """
        Retrieves context, optionally filtering by memory type and hydrating structured memories.
        """
        if memory_types is None:
            memory_types = ["semantic", "episodic", "procedural"]
            
        # If we need all types, we can just query without filter and hydrate.
        # But ChromaDB doesn't support OR in simple where clause easily for lists in some versions.
        # We will query ChromaDB, then filter/hydrate in Python.
        
        results = self.long_term.retrieve_context(query, n_results=max_results * 2) # Over-fetch
        
        docs = results.get('documents', [[]])[0]
        metadatas = results.get('metadatas', [[]])[0]
        
        final_results = []
        
        for doc, meta in zip(docs, metadatas):
            m_type = meta.get("type", "semantic")
            
            if m_type not in memory_types:
                continue
                
            if m_type == "episodic":
                # Hydrate from SQLite
                mem_id = meta.get("id")
                full_mem = self.structured.get_episodic(mem_id)
                if full_mem:
                    final_results.append({"type": "episodic", "data": full_mem})
            elif m_type == "procedural":
                mem_id = meta.get("id")
                full_mem = self.structured.get_procedural(mem_id)
                if full_mem and full_mem.get("enabled", True):
                    final_results.append({"type": "procedural", "data": full_mem})
            else:
                final_results.append({"type": "semantic", "data": doc})
                
            if len(final_results) >= max_results:
                break
        
        observability_manager.emit_event(ObservabilityEvent(
            event_type="MEMORY_RETRIEVED",
            metadata={
                "query": query,
                "number_of_results": len(final_results),
                "types_requested": memory_types
            }
        ))
        
        return final_results

    def save_episodic_memory(self, memory: EpisodicMemory):
        """Saves an episodic memory to SQLite and embeds it in ChromaDB."""
        if self.structured.save_episodic(memory):
            doc = f"Event: {memory.summary}\nOutcome: {memory.outcome}"
            meta = {"type": "episodic", "id": memory.memory_id}
            self.long_term.store_memory(document=doc, metadata=meta, doc_id=memory.memory_id)
            
            observability_manager.emit_event(ObservabilityEvent(
                event_type="EPISODIC_MEMORY_CREATED",
                metadata={"memory_id": memory.memory_id, "task_id": memory.task_id}
            ))

    def save_procedural_memory(self, memory: ProceduralMemory):
        """Saves a procedural memory to SQLite and embeds the trigger in ChromaDB."""
        if self.structured.save_procedural(memory):
            doc = f"Procedure: {memory.name}\nTrigger: {memory.trigger}\nDescription: {memory.description}"
            meta = {"type": "procedural", "id": memory.procedure_id}
            self.long_term.store_memory(document=doc, metadata=meta, doc_id=memory.procedure_id)
            
            observability_manager.emit_event(ObservabilityEvent(
                event_type="PROCEDURAL_MEMORY_CREATED",
                metadata={"procedure_id": memory.procedure_id, "name": memory.name}
            ))
            
    def delete_memory(self, memory_id: str, memory_type: MemoryType):
        """Deletes a memory from both SQLite and ChromaDB."""
        if memory_type == MemoryType.EPISODIC:
            self.structured.delete_episodic(memory_id)
        elif memory_type == MemoryType.PROCEDURAL:
            self.structured.delete_procedural(memory_id)
            
        self.long_term.delete_memory(memory_id)
        
        observability_manager.emit_event(ObservabilityEvent(
            event_type="MEMORY_DELETED",
            metadata={"memory_id": memory_id, "type": memory_type.value}
        ))
