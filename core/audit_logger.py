import sqlite3
import json
import uuid
import threading
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

@dataclass
class AuditEvent:
    event_id: str
    timestamp: str
    task_id: str
    agent: str
    tool: str
    action: str
    target: str
    risk_level: str
    permission_status: str
    confirmation_status: str
    execution_status: str
    verification_status: str
    result: str
    evidence: str
    duration_ms: int
    files_changed: str = ""

class SQLiteAuditLogger:
    """
    Centralized, fail-safe Audit Logger that writes to an SQLite database.
    Provides chronological append-oriented storage and query capabilities.
    """
    def __init__(self, db_path: str = "audit.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """Initializes the database schema if it doesn't exist."""
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                try:
                    cursor = conn.cursor()
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS audit_events (
                            event_id TEXT PRIMARY KEY,
                            timestamp TEXT,
                            task_id TEXT,
                            agent TEXT,
                            tool TEXT,
                            action TEXT,
                            target TEXT,
                            risk_level TEXT,
                            permission_status TEXT,
                            confirmation_status TEXT,
                            execution_status TEXT,
                            verification_status TEXT,
                            result TEXT,
                            evidence TEXT,
                            duration_ms INTEGER,
                            files_changed TEXT
                        )
                    ''')
                    # Migrate existing table if files_changed column is missing
                    cursor.execute("PRAGMA table_info(audit_events)")
                    columns = [row[1] for row in cursor.fetchall()]
                    if "files_changed" not in columns:
                        cursor.execute("ALTER TABLE audit_events ADD COLUMN files_changed TEXT")
                    
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS a2a_messages (
                            message_id TEXT PRIMARY KEY,
                            timestamp TEXT,
                            task_id TEXT,
                            node_id TEXT,
                            parent_task_id TEXT,
                            sender_agent TEXT,
                            recipient_agent TEXT,
                            message_type TEXT,
                            status TEXT,
                            result TEXT,
                            evidence TEXT,
                            errors TEXT,
                            files_changed TEXT,
                            recommended_next_steps TEXT
                        )
                    ''')
                    conn.commit()
                finally:
                    conn.close()
        except Exception as e:
            print(f"[AUDIT LOGGER ERROR] Failed to initialize DB: {e}")

    def _sanitize_string(self, value: Any, max_len: int = 1000) -> str:
        """Safely converts to string and truncates extremely large dumps."""
        if value is None:
            return ""
        s = str(value)
        return s if len(s) <= max_len else s[:max_len] + "... [TRUNCATED]"

    def log_event(self, event: AuditEvent) -> bool:
        """
        Persists the audit event. Fails safely without crashing the main thread.
        """
        try:
            event_dict = asdict(event)
            # Sanitize large fields to prevent DB bloat
            event_dict['result'] = self._sanitize_string(event_dict['result'], 2000)
            event_dict['evidence'] = self._sanitize_string(event_dict['evidence'], 2000)
            
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                try:
                    cursor = conn.cursor()
                    columns = ', '.join(event_dict.keys())
                    placeholders = ', '.join(['?'] * len(event_dict))
                    cursor.execute(
                        f"INSERT INTO audit_events ({columns}) VALUES ({placeholders})",
                        list(event_dict.values())
                    )
                    conn.commit()
                finally:
                    conn.close()
            return True
        except Exception as e:
            # PRD Requirement: Audit failure must NOT silently turn a successful action into a fake failure.
            print(f"\n[CRITICAL AUDIT FAILURE] Failed to write audit event for tool '{event.tool}'. Reason: {e}")
            print(f"Fallback Event Dump: {event_dict}")
            return False

    def query_events(self, 
                     agent: Optional[str] = None, 
                     task_id: Optional[str] = None, 
                     tool: Optional[str] = None,
                     risk_level: Optional[str] = None,
                     execution_status: Optional[str] = None,
                     limit: int = 100) -> List[Dict[str, Any]]:
        """Queries recent events with basic filtering."""
        try:
            query = "SELECT * FROM audit_events WHERE 1=1"
            params = []
            
            if agent:
                query += " AND agent = ?"
                params.append(agent)
            if task_id:
                query += " AND task_id = ?"
                params.append(task_id)
            if tool:
                query += " AND tool = ?"
                params.append(tool)
            if risk_level:
                query += " AND risk_level = ?"
                params.append(risk_level)
            if execution_status:
                query += " AND execution_status = ?"
                params.append(execution_status)
                
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                try:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute(query, params)
                    rows = cursor.fetchall()
                    return [dict(row) for row in rows]
                finally:
                    conn.close()
        except Exception as e:
            print(f"[AUDIT QUERY ERROR] {e}")
            return []

    def log_a2a_message(self, message) -> bool:
        """
        Persists an A2A message to the audit log.
        """
        try:
            msg_dict = message.model_dump()
            
            # Serialize complex types to JSON strings for SQLite
            msg_dict['evidence'] = json.dumps(msg_dict['evidence'])
            msg_dict['errors'] = json.dumps([e if isinstance(e, dict) else e for e in msg_dict['errors']])
            msg_dict['files_changed'] = json.dumps([f if isinstance(f, dict) else f for f in msg_dict['files_changed']])
            msg_dict['recommended_next_steps'] = json.dumps(msg_dict['recommended_next_steps'])
            
            # Convert enums to strings
            if hasattr(msg_dict['message_type'], 'value'):
                msg_dict['message_type'] = msg_dict['message_type'].value
            if hasattr(msg_dict['status'], 'value'):
                msg_dict['status'] = msg_dict['status'].value
                
            # Rename created_at to timestamp for schema alignment
            msg_dict['timestamp'] = msg_dict.pop('created_at', datetime.utcnow().isoformat() + "Z")
            
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                try:
                    cursor = conn.cursor()
                    columns = ', '.join(msg_dict.keys())
                    placeholders = ', '.join(['?'] * len(msg_dict))
                    cursor.execute(
                        f"INSERT INTO a2a_messages ({columns}) VALUES ({placeholders})",
                        list(msg_dict.values())
                    )
                    conn.commit()
                finally:
                    conn.close()
            return True
        except Exception as e:
            print(f"\n[CRITICAL AUDIT FAILURE] Failed to write A2A message '{message.message_id}'. Reason: {e}")
            return False
