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
                            recommended_next_steps TEXT,
                            attempt INTEGER,
                            recovery_action TEXT,
                            session_id TEXT,
                            approval_id TEXT
                        )
                    ''')
                    # Migrate existing a2a_messages table if columns are missing
                    cursor.execute("PRAGMA table_info(a2a_messages)")
                    a2a_cols = [row[1] for row in cursor.fetchall()]
                    if "attempt" not in a2a_cols:
                        cursor.execute("ALTER TABLE a2a_messages ADD COLUMN attempt INTEGER")
                    if "recovery_action" not in a2a_cols:
                        cursor.execute("ALTER TABLE a2a_messages ADD COLUMN recovery_action TEXT")
                    if "session_id" not in a2a_cols:
                        cursor.execute("ALTER TABLE a2a_messages ADD COLUMN session_id TEXT")
                    if "approval_id" not in a2a_cols:
                        cursor.execute("ALTER TABLE a2a_messages ADD COLUMN approval_id TEXT")
                    
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS recovery_events (
                            event_id TEXT PRIMARY KEY,
                            timestamp TEXT,
                            task_id TEXT,
                            node_id TEXT,
                            agent TEXT,
                            attempt INTEGER,
                            failure_category TEXT,
                            recovery_action TEXT,
                            reason TEXT,
                            outcome TEXT,
                            metadata TEXT
                        )
                    ''')
                    
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS session_states (
                            session_id TEXT PRIMARY KEY,
                            conversation_id TEXT,
                            session_status TEXT,
                            current_request TEXT,
                            current_intent TEXT,
                            active_task_id TEXT,
                            active_task_graph_id TEXT,
                            active_node_id TEXT,
                            active_agent TEXT,
                            pending_clarification INTEGER,
                            clarification_prompt TEXT,
                            clarification_history TEXT,
                            recent_verified_results TEXT,
                            recent_failures TEXT,
                            current_context_reference TEXT,
                            user_approved_actions TEXT,
                            created_at TEXT,
                            updated_at TEXT,
                            metadata TEXT
                        )
                    ''')
                    
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS session_events (
                            event_id TEXT PRIMARY KEY,
                            timestamp TEXT,
                            session_id TEXT,
                            conversation_id TEXT,
                            task_id TEXT,
                            node_id TEXT,
                            previous_state TEXT,
                            new_state TEXT,
                            reason TEXT,
                            metadata TEXT
                        )
                    ''')
                    
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS approval_requests (
                            approval_id TEXT PRIMARY KEY,
                            session_id TEXT,
                            task_id TEXT,
                            node_id TEXT,
                            tool_name TEXT,
                            risk_level TEXT,
                            action_description TEXT,
                            requested_at TEXT,
                            expires_at TEXT,
                            status TEXT,
                            approved_by TEXT,
                            approval_reason TEXT,
                            metadata TEXT
                        )
                    ''')
                    
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS approval_events (
                            event_id TEXT PRIMARY KEY,
                            timestamp TEXT,
                            approval_id TEXT,
                            session_id TEXT,
                            task_id TEXT,
                            node_id TEXT,
                            tool_name TEXT,
                            previous_status TEXT,
                            new_status TEXT,
                            actor TEXT,
                            reason TEXT,
                            metadata TEXT
                        )
                    ''')
                    
                    cursor.execute("PRAGMA table_info(a2a_messages)")
                    a2a_cols = [row[1] for row in cursor.fetchall()]
                    if "session_id" not in a2a_cols:
                        cursor.execute("ALTER TABLE a2a_messages ADD COLUMN session_id TEXT")
                        
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

    def log_recovery_event(
        self,
        task_id: str,
        node_id: str,
        agent: str,
        attempt: int,
        failure_category: str,
        recovery_action: str,
        reason: str,
        outcome: str = "PENDING",
        metadata: Dict[str, Any] = None
    ) -> bool:
        """
        Persists a recovery decision or retry attempt to the audit log.
        """
        try:
            event_id = str(uuid.uuid4())
            timestamp = datetime.utcnow().isoformat() + "Z"
            meta_json = json.dumps(metadata or {})
            
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                try:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO recovery_events 
                        (event_id, timestamp, task_id, node_id, agent, attempt, failure_category, recovery_action, reason, outcome, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (event_id, timestamp, task_id, node_id, agent, attempt, failure_category, recovery_action, reason, outcome, meta_json))
                    conn.commit()
                finally:
                    conn.close()
            return True
        except Exception as e:
            print(f"\n[CRITICAL AUDIT FAILURE] Failed to write recovery event for node '{node_id}'. Reason: {e}")
            return False

    def query_recovery_events(self, task_id: Optional[str] = None, node_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Queries recovery events."""
        try:
            query = "SELECT * FROM recovery_events WHERE 1=1"
            params = []
            if task_id:
                query += " AND task_id = ?"
                params.append(task_id)
            if node_id:
                query += " AND node_id = ?"
                params.append(node_id)
            query += " ORDER BY timestamp ASC LIMIT ?"
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
            print(f"[AUDIT QUERY RECOVERY ERROR] {e}")
            return []

    def log_session_event(
        self,
        session_id: str,
        previous_state: str,
        new_state: str,
        reason: str = "",
        conversation_id: Optional[str] = None,
        task_id: Optional[str] = None,
        node_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Logs an operational session transition event."""
        try:
            event_id = str(uuid.uuid4())
            timestamp = datetime.utcnow().isoformat() + "Z"
            meta_json = json.dumps(metadata or {})
            
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                try:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO session_events (
                            event_id, timestamp, session_id, conversation_id, task_id, node_id,
                            previous_state, new_state, reason, metadata
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (event_id, timestamp, session_id, conversation_id, task_id, node_id,
                          previous_state, new_state, reason, meta_json))
                    conn.commit()
                finally:
                    conn.close()
            return True
        except Exception as e:
            print(f"[AUDIT LOGGER ERROR] Failed to log session event: {e}")
            return False

    def query_session_events(self, session_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Queries session transition events."""
        try:
            query = "SELECT * FROM session_events WHERE 1=1"
            params = []
            if session_id:
                query += " AND session_id = ?"
                params.append(session_id)
            query += " ORDER BY timestamp ASC LIMIT ?"
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
            print(f"[AUDIT QUERY SESSION EVENTS ERROR] {e}")
            return []

    def save_session_state(self, session_dict: Dict[str, Any]) -> bool:
        """Persists or updates an active SessionState."""
        try:
            sid = session_dict.get("session_id")
            if not sid:
                return False
            
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                try:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT OR REPLACE INTO session_states (
                            session_id, conversation_id, session_status, current_request,
                            current_intent, active_task_id, active_task_graph_id, active_node_id,
                            active_agent, pending_clarification, clarification_prompt,
                            clarification_history, recent_verified_results, recent_failures,
                            current_context_reference, user_approved_actions, created_at,
                            updated_at, metadata
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        sid,
                        session_dict.get("conversation_id"),
                        session_dict.get("session_status"),
                        session_dict.get("current_request", ""),
                        json.dumps(session_dict.get("current_intent") or {}),
                        session_dict.get("active_task_id"),
                        session_dict.get("active_task_graph_id"),
                        session_dict.get("active_node_id"),
                        session_dict.get("active_agent"),
                        1 if session_dict.get("pending_clarification") else 0,
                        session_dict.get("clarification_prompt"),
                        json.dumps(session_dict.get("clarification_history") or []),
                        json.dumps(session_dict.get("recent_verified_results") or []),
                        json.dumps(session_dict.get("recent_failures") or []),
                        json.dumps(session_dict.get("current_context_reference") or {}),
                        json.dumps(session_dict.get("user_approved_actions") or []),
                        session_dict.get("created_at"),
                        session_dict.get("updated_at"),
                        json.dumps(session_dict.get("metadata") or {})
                    ))
                    conn.commit()
                finally:
                    conn.close()
            return True
        except Exception as e:
            print(f"[AUDIT SAVE SESSION ERROR] {e}")
            return False

    def load_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Loads persisted SessionState by session_id."""
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                try:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM session_states WHERE session_id = ?", (session_id,))
                    row = cursor.fetchone()
                    if not row:
                        return None
                    d = dict(row)
                    d["pending_clarification"] = bool(d.get("pending_clarification"))
                    for key in ["current_intent", "clarification_history", "recent_verified_results",
                                "recent_failures", "current_context_reference", "user_approved_actions", "metadata"]:
                        if d.get(key) and isinstance(d[key], str):
                            try:
                                d[key] = json.loads(d[key])
                            except Exception:
                                pass
                    return d
                finally:
                    conn.close()
        except Exception as e:
            print(f"[AUDIT LOAD SESSION ERROR] {e}")
            return None

    # ── Task 14: Approval Requests & Events Persistence ────────────────────────
    def save_approval_request(self, req_dict: Dict[str, Any]) -> bool:
        """Persists or updates an ApprovalRequest in SQLite."""
        try:
            status_val = req_dict.get("status")
            if hasattr(status_val, 'value'):
                status_str = status_val.value
            else:
                status_str = str(status_val).replace("ApprovalStatus.", "")

            risk_val = req_dict.get("risk_level")
            if hasattr(risk_val, 'value'):
                risk_str = risk_val.value
            elif hasattr(risk_val, 'name'):
                risk_str = risk_val.name
            else:
                risk_str = str(risk_val).replace("RiskLevel.", "")

            with self._lock:
                conn = sqlite3.connect(self.db_path)
                try:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT OR REPLACE INTO approval_requests (
                            approval_id, session_id, task_id, node_id, tool_name,
                            risk_level, action_description, requested_at, expires_at,
                            status, approved_by, approval_reason, metadata
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        req_dict.get("approval_id"),
                        req_dict.get("session_id"),
                        req_dict.get("task_id"),
                        req_dict.get("node_id"),
                        req_dict.get("tool_name"),
                        risk_str,
                        req_dict.get("action_description", ""),
                        req_dict.get("requested_at"),
                        req_dict.get("expires_at"),
                        status_str,
                        req_dict.get("approved_by"),
                        req_dict.get("approval_reason"),
                        json.dumps(req_dict.get("metadata") or {})
                    ))
                    conn.commit()
                finally:
                    conn.close()
            return True
        except Exception as e:
            print(f"[AUDIT SAVE APPROVAL ERROR] {e}")
            return False

    def load_approval_request(self, approval_id: str) -> Optional[Dict[str, Any]]:
        """Loads an ApprovalRequest by approval_id."""
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                try:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM approval_requests WHERE approval_id = ?", (approval_id,))
                    row = cursor.fetchone()
                    if not row:
                        return None
                    d = dict(row)
                    if d.get("status"):
                        d["status"] = str(d["status"]).replace("ApprovalStatus.", "")
                    if d.get("risk_level"):
                        r_str = str(d["risk_level"]).replace("RiskLevel.", "")
                        try:
                            d["risk_level"] = int(r_str)
                        except ValueError:
                            from core.execution_gate import RiskLevel
                            d["risk_level"] = getattr(RiskLevel, r_str, RiskLevel.READ_ONLY)
                    if d.get("metadata") and isinstance(d["metadata"], str):
                        try:
                            d["metadata"] = json.loads(d["metadata"])
                        except Exception:
                            pass
                    return d
                finally:
                    conn.close()
        except Exception as e:
            print(f"[AUDIT LOAD APPROVAL ERROR] {e}")
            return None
        except Exception as e:
            print(f"[AUDIT LOAD APPROVAL ERROR] {e}")
            return None

    def query_approval_requests(self, session_id: Optional[str] = None, task_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Queries approval requests with optional filters."""
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                try:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    query = "SELECT * FROM approval_requests WHERE 1=1"
                    params = []
                    if session_id:
                        query += " AND session_id = ?"
                        params.append(session_id)
                    if task_id:
                        query += " AND task_id = ?"
                        params.append(task_id)
                    if status:
                        query += " AND status = ?"
                        params.append(status)
                    cursor.execute(query, params)
                    rows = cursor.fetchall()
                    results = []
                    for row in rows:
                        d = dict(row)
                        if d.get("metadata") and isinstance(d["metadata"], str):
                            try:
                                d["metadata"] = json.loads(d["metadata"])
                            except Exception:
                                pass
                        results.append(d)
                    return results
                finally:
                    conn.close()
        except Exception as e:
            print(f"[AUDIT QUERY APPROVALS ERROR] {e}")
            return []

    def log_approval_event(
        self,
        approval_id: str,
        session_id: str,
        task_id: str,
        tool_name: str,
        previous_status: str,
        new_status: str,
        node_id: Optional[str] = None,
        actor: str = "User",
        reason: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Logs an approval lifecycle transition event."""
        try:
            event_id = str(uuid.uuid4())
            import datetime
            timestamp = datetime.datetime.now().isoformat() + "Z"
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                try:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO approval_events (
                            event_id, timestamp, approval_id, session_id, task_id,
                            node_id, tool_name, previous_status, new_status, actor, reason, metadata
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        event_id,
                        timestamp,
                        approval_id,
                        session_id,
                        task_id,
                        node_id or "",
                        tool_name,
                        previous_status,
                        new_status,
                        actor,
                        reason,
                        json.dumps(metadata or {})
                    ))
                    conn.commit()
                finally:
                    conn.close()
            return True
        except Exception as e:
            print(f"[AUDIT LOG APPROVAL EVENT ERROR] {e}")
            return False

    def query_approval_events(self, approval_id: Optional[str] = None, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Queries approval lifecycle events."""
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                try:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    query = "SELECT * FROM approval_events WHERE 1=1"
                    params = []
                    if approval_id:
                        query += " AND approval_id = ?"
                        params.append(approval_id)
                    if session_id:
                        query += " AND session_id = ?"
                        params.append(session_id)
                    query += " ORDER BY timestamp ASC"
                    cursor.execute(query, params)
                    rows = cursor.fetchall()
                    results = []
                    for row in rows:
                        d = dict(row)
                        if d.get("metadata") and isinstance(d["metadata"], str):
                            try:
                                d["metadata"] = json.loads(d["metadata"])
                            except Exception:
                                pass
                        results.append(d)
                    return results
                finally:
                    conn.close()
        except Exception as e:
            print(f"[AUDIT QUERY APPROVAL EVENTS ERROR] {e}")
            return []
