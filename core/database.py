import os
from datetime import datetime
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import chromadb
from dotenv import load_dotenv

load_dotenv()

class ShortTermMemory:
    """
    Handles logging daily activities, raw system commands, and task queues 
    into a local MongoDB database.
    """
    def __init__(self):
        self.mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
        self.db_name = os.getenv("MONGO_DB_NAME", "jarvis_db")
        self.client = None
        self.db = None
        self._connect()

    def _connect(self):
        """Establishes connection to MongoDB."""
        try:
            # serverSelectionTimeoutMS is set to quickly fail if DB is not up
            self.client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=3000)
            self.client.admin.command('ping') # Trigger a call to verify connection
            self.db = self.client[self.db_name]
            print(f"[OK] Successfully connected to MongoDB at {self.mongo_uri}")
        except ConnectionFailure:
            print(f"[WARN] MongoDB not reachable at {self.mongo_uri}. Running without short-term memory.")
            self.client = None
            self.db = None
        except Exception as e:
            print(f"[WARN] MongoDB init error: {e}. Running without short-term memory.")
            self.client = None
            self.db = None

    def log_activity(self, collection_name, data):
        """
        Logs an activity or command into MongoDB.
        
        Args:
            collection_name (str): The name of the collection (e.g., 'interaction_logs').
            data (dict): The data payload to store.
            
        Returns:
            str: The stringified ID of the inserted document, or None if failed.
        """
        if self.db is None:
            print("[WARN] MongoDB is not connected. Skipping log.")
            return None
        
        try:
            collection = self.db[collection_name]
            data['timestamp'] = datetime.utcnow()
            result = collection.insert_one(data)
            return str(result.inserted_id)
        except Exception as e:
            print(f"[ERROR] Error writing to MongoDB: {e}")
            return None


class LongTermMemory:
    """
    Handles storing user conversations and project context as vector embeddings 
    in ChromaDB for semantic retrieval.
    """
    def __init__(self):
        self.db_path = os.getenv("CHROMA_DB_PATH", "./chroma_db")
        self.client = None
        self.collection = None
        self._connect()

    def _connect(self):
        """Initializes ChromaDB client and creates a default collection."""
        try:
            # Ensure the directory exists
            os.makedirs(self.db_path, exist_ok=True)
            self.client = chromadb.PersistentClient(path=self.db_path)
            # Default collection for conversation history
            self.collection = self.client.get_or_create_collection(name="contextual_memory")
            print(f"[OK] Successfully initialized ChromaDB at {self.db_path}")
        except Exception as e:
            print(f"[ERROR] Error initializing ChromaDB: {e}")
            self.client = None
            self.collection = None

    def store_memory(self, document, metadata=None, doc_id=None):
        """
        Stores a document as a vector embedding.
        
        Args:
            document (str): The text content to store.
            metadata (dict, optional): Associated metadata.
            doc_id (str, optional): Unique ID for the document.
        """
        if self.collection is None:
            print("[WARN] ChromaDB is not connected. Skipping storage.")
            return

        try:
            if doc_id is None:
                doc_id = str(datetime.utcnow().timestamp())
                
            self.collection.add(
                documents=[document],
                metadatas=[metadata] if metadata else [{}],
                ids=[doc_id]
            )
        except Exception as e:
            print(f"[ERROR] Error writing to ChromaDB: {e}")

    def retrieve_context(self, query, n_results=3):
        """
        Retrieves historical context based on semantic similarity.
        
        Args:
            query (str): The search query.
            n_results (int): Number of similar documents to retrieve.
            
        Returns:
            list: List of document strings that match the query.
        """
        if self.collection is None:
            print("[WARN] ChromaDB is not connected. Returning empty context.")
            return []

        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results
            )
            return results.get('documents', [[]])[0]
        except Exception as e:
            print(f"[ERROR] Error querying ChromaDB: {e}")
            return []
