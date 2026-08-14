import os
from datetime import datetime
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import chromadb
import sqlite3
import json
import threading
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

    def retrieve_context(self, query, n_results=3, metadata_filter=None):
        """
        Retrieves historical context based on semantic similarity.
        
        Args:
            query (str): The search query.
            n_results (int): Number of similar documents to retrieve.
            metadata_filter (dict, optional): ChromaDB metadata filter.
            
        Returns:
            list: List of document strings or full results if structured.
        """
        if self.collection is None:
            print("[WARN] ChromaDB is not connected. Returning empty context.")
            return []

        try:
            kwargs = {
                "query_texts": [query],
                "n_results": n_results
            }
            if metadata_filter:
                kwargs["where"] = metadata_filter

            results = self.collection.query(**kwargs)
            return results
        except Exception as e:
            print(f"[ERROR] Error querying ChromaDB: {e}")
            return {"documents": [[]], "metadatas": [[]], "ids": [[]]}
            
    def delete_memory(self, doc_id: str):
        if self.collection is None:
            return
        try:
            self.collection.delete(ids=[doc_id])
        except Exception as e:
            print(f"[ERROR] Error deleting from ChromaDB: {e}")


class StructuredMemoryStore:
    """
    Handles structured, relational storage for Episodic and Procedural memories 
    using SQLite to ensure ACID compliance and zero dependency footprint.
    Reuses the same database file as AuditLogger to minimize files.
    """
    def __init__(self, db_path: str = "audit.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                try:
                    cursor = conn.cursor()
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS episodic_memory (
                            memory_id TEXT PRIMARY KEY,
                            timestamp TEXT,
                            task_id TEXT,
                            session_id TEXT,
                            event_type TEXT,
                            summary TEXT,
                            outcome TEXT,
                            evidence_reference TEXT,
                            agents_involved TEXT,
                            tags TEXT,
                            created_at TEXT,
                            updated_at TEXT
                        )
                    ''')
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS procedural_memory (
                            procedure_id TEXT PRIMARY KEY,
                            name TEXT,
                            description TEXT,
                            trigger TEXT,
                            steps TEXT,
                            dependencies TEXT,
                            required_capabilities TEXT,
                            risk_profile TEXT,
                            verification_requirements TEXT,
                            enabled BOOLEAN,
                            created_at TEXT,
                            updated_at TEXT,
                            last_used TEXT,
                            success_count INTEGER,
                            failure_count INTEGER
                        )
                    ''')
                    conn.commit()
                finally:
                    conn.close()
        except Exception as e:
            print(f"[MEMORY DB ERROR] Failed to initialize Structured Memory: {e}")

    def save_episodic(self, memory):
        try:
            d = memory.model_dump()
            d['agents_involved'] = json.dumps(d['agents_involved'])
            d['tags'] = json.dumps(d['tags'])
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                try:
                    cursor = conn.cursor()
                    columns = ', '.join(d.keys())
                    placeholders = ', '.join(['?'] * len(d))
                    cursor.execute(f"INSERT OR REPLACE INTO episodic_memory ({columns}) VALUES ({placeholders})", list(d.values()))
                    conn.commit()
                finally:
                    conn.close()
            return True
        except Exception as e:
            print(f"[MEMORY DB ERROR] {e}")
            return False

    def save_procedural(self, memory):
        try:
            d = memory.model_dump()
            d['steps'] = json.dumps(d['steps'])
            d['dependencies'] = json.dumps(d['dependencies'])
            d['required_capabilities'] = json.dumps(d['required_capabilities'])
            d['verification_requirements'] = json.dumps(d['verification_requirements'])
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                try:
                    cursor = conn.cursor()
                    columns = ', '.join(d.keys())
                    placeholders = ', '.join(['?'] * len(d))
                    cursor.execute(f"INSERT OR REPLACE INTO procedural_memory ({columns}) VALUES ({placeholders})", list(d.values()))
                    conn.commit()
                finally:
                    conn.close()
            return True
        except Exception as e:
            print(f"[MEMORY DB ERROR] {e}")
            return False

    def get_episodic(self, memory_id: str):
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM episodic_memory WHERE memory_id = ?", (memory_id,))
                row = cursor.fetchone()
                conn.close()
                if row:
                    d = dict(row)
                    d['agents_involved'] = json.loads(d['agents_involved'])
                    d['tags'] = json.loads(d['tags'])
                    return d
                return None
        except Exception as e:
            print(f"[MEMORY DB ERROR] {e}")
            return None

    def get_procedural(self, procedure_id: str):
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM procedural_memory WHERE procedure_id = ?", (procedure_id,))
                row = cursor.fetchone()
                conn.close()
                if row:
                    d = dict(row)
                    d['steps'] = json.loads(d['steps'])
                    d['dependencies'] = json.loads(d['dependencies'])
                    d['required_capabilities'] = json.loads(d['required_capabilities'])
                    d['verification_requirements'] = json.loads(d['verification_requirements'])
                    d['enabled'] = bool(d['enabled'])
                    return d
                return None
        except Exception as e:
            print(f"[MEMORY DB ERROR] {e}")
            return None

    def delete_episodic(self, memory_id: str):
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM episodic_memory WHERE memory_id = ?", (memory_id,))
                conn.commit()
                conn.close()
        except Exception as e:
            print(f"[MEMORY DB ERROR] {e}")

    def delete_procedural(self, procedure_id: str):
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM procedural_memory WHERE procedure_id = ?", (procedure_id,))
                conn.commit()
                conn.close()
        except Exception as e:
            print(f"[MEMORY DB ERROR] {e}")

class EnvironmentStore:
    """
    Handles structured storage for EnvironmentKnowledge using SQLite.
    """
    def __init__(self, db_path: str = "audit.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                try:
                    cursor = conn.cursor()
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS environment_index (
                            project_root TEXT PRIMARY KEY,
                            environment_id TEXT,
                            last_scanned TEXT,
                            data TEXT
                        )
                    ''')
                    conn.commit()
                finally:
                    conn.close()
        except Exception as e:
            print(f"[ENV DB ERROR] Failed to initialize Environment Index: {e}")

    def save_environment(self, env_knowledge) -> bool:
        """Saves an EnvironmentKnowledge model to SQLite."""
        try:
            d = env_knowledge.model_dump()
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT OR REPLACE INTO environment_index (project_root, environment_id, last_scanned, data) VALUES (?, ?, ?, ?)",
                        (d["project_root"], d["environment_id"], d["last_scanned"], json.dumps(d))
                    )
                    conn.commit()
                finally:
                    conn.close()
            return True
        except Exception as e:
            print(f"[ENV DB ERROR] {e}")
            return False

    def get_environment(self, project_root: str):
        """Retrieves an EnvironmentKnowledge dictionary for a project root."""
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT data FROM environment_index WHERE project_root = ?", (project_root,))
                row = cursor.fetchone()
                conn.close()
                if row:
                    return json.loads(row["data"])
                return None
        except Exception as e:
            print(f"[ENV DB ERROR] {e}")
            return None
