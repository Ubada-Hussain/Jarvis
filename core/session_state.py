import os
import re
import json
import uuid
import datetime
import threading
from enum import Enum
from typing import Dict, List, Any, Optional, Set
from pydantic import BaseModel, Field

from core.observability import observability_manager, ObservabilityEvent
from core.audit_logger import SQLiteAuditLogger

class SessionStatus(str, Enum):
    NEW = "NEW"
    ACTIVE = "ACTIVE"
    WAITING_FOR_CLARIFICATION = "WAITING_FOR_CLARIFICATION"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    RECOVERING = "RECOVERING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

# Valid state transition rules (Task 13 Phase Lifecycle)
ALLOWED_TRANSITIONS: Dict[SessionStatus, Set[SessionStatus]] = {
    SessionStatus.NEW: {
        SessionStatus.ACTIVE,
        SessionStatus.PLANNING,
        SessionStatus.EXECUTING,
        SessionStatus.WAITING_FOR_CLARIFICATION,
        SessionStatus.CANCELLED
    },
    SessionStatus.ACTIVE: {
        SessionStatus.PLANNING,
        SessionStatus.WAITING_FOR_CLARIFICATION,
        SessionStatus.EXECUTING,
        SessionStatus.CANCELLED
    },
    SessionStatus.PLANNING: {
        SessionStatus.WAITING_FOR_CLARIFICATION,
        SessionStatus.EXECUTING,
        SessionStatus.FAILED,
        SessionStatus.CANCELLED
    },
    SessionStatus.WAITING_FOR_CLARIFICATION: {
        SessionStatus.PLANNING,
        SessionStatus.CANCELLED,
        SessionStatus.FAILED
    },
    SessionStatus.EXECUTING: {
        SessionStatus.RECOVERING,
        SessionStatus.COMPLETED,
        SessionStatus.FAILED,
        SessionStatus.CANCELLED
    },
    SessionStatus.RECOVERING: {
        SessionStatus.EXECUTING,
        SessionStatus.COMPLETED,
        SessionStatus.FAILED,
        SessionStatus.CANCELLED
    },
    SessionStatus.COMPLETED: {
        SessionStatus.PLANNING,
        SessionStatus.NEW
    },
    SessionStatus.FAILED: {
        SessionStatus.PLANNING,
        SessionStatus.RECOVERING
    },
    SessionStatus.CANCELLED: {
        SessionStatus.NEW,
        SessionStatus.PLANNING
    }
}

class SessionState(BaseModel):
    """
    Canonical SessionState Model (Task 13).
    Tracks operational session and conversation lifecycle.
    """
    session_id: str
    conversation_id: Optional[str] = None
    current_request: str = ""
    current_intent: Optional[Dict[str, Any]] = None
    active_task_id: Optional[str] = None
    active_task_graph_id: Optional[str] = None
    active_node_id: Optional[str] = None
    active_agent: Optional[str] = None
    pending_clarification: bool = False
    clarification_prompt: Optional[str] = None
    clarification_history: List[Dict[str, Any]] = Field(default_factory=list)
    recent_verified_results: List[Dict[str, Any]] = Field(default_factory=list)
    recent_failures: List[Dict[str, Any]] = Field(default_factory=list)
    current_context_reference: Optional[Dict[str, Any]] = None
    user_approved_actions: List[str] = Field(default_factory=list)
    pending_approvals: List[str] = Field(default_factory=list)
    approved_actions: List[Dict[str, Any]] = Field(default_factory=list)
    denied_actions: List[Dict[str, Any]] = Field(default_factory=list)
    session_status: SessionStatus = SessionStatus.NEW
    created_at: str = Field(default_factory=lambda: datetime.datetime.now().isoformat() + "Z")
    updated_at: str = Field(default_factory=lambda: datetime.datetime.now().isoformat() + "Z")
    metadata: Dict[str, Any] = Field(default_factory=dict)

def sanitize_session_data(data: Any) -> Any:
    """Recursively redacts secrets and credentials from session payloads."""
    SECRET_PATTERNS = ["password", "token", "secret", "api_key", "auth", "credential", "private_key", "access_key"]
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            k_lower = k.lower()
            if any(s == k_lower or k_lower.startswith(s + "_") or k_lower.endswith("_" + s) or s in k_lower.split("_") for s in SECRET_PATTERNS):
                sanitized[k] = "******"
            else:
                sanitized[k] = sanitize_session_data(v)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_session_data(x) for x in data]
    elif isinstance(data, str):
        # Redact common key patterns
        s = re.sub(r'(api_key|token|password|secret)=([^&\s]+)', r'\1=******', data, flags=re.IGNORECASE)
        return s
    return data

class SessionManager:
    """
    Central Manager for SessionState lifecycle, isolation, persistence, and transitions.
    """
    def __init__(self, audit_logger: Optional[SQLiteAuditLogger] = None, approval_manager=None):
        self.audit_logger = audit_logger or SQLiteAuditLogger()
        self.approval_manager = approval_manager
        self._sessions: Dict[str, SessionState] = {}
        self._lock = threading.RLock()

    def create_session(
        self,
        conversation_id: Optional[str] = None,
        initial_request: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> SessionState:
        """Creates a new isolated SessionState."""
        session_id = f"sess-{uuid.uuid4()}"
        clean_meta = sanitize_session_data(metadata or {})
        clean_req = sanitize_session_data(initial_request)
        
        session = SessionState(
            session_id=session_id,
            conversation_id=conversation_id or f"conv-{uuid.uuid4()}",
            current_request=clean_req,
            metadata=clean_meta
        )
        
        with self._lock:
            self._sessions[session_id] = session
            
        self.save_session(session)
        
        observability_manager.emit_event(ObservabilityEvent(
            event_type="SESSION_CREATED",
            metadata={"session_id": session_id, "conversation_id": session.conversation_id}
        ))
        
        self.audit_logger.log_session_event(
            session_id=session_id,
            conversation_id=session.conversation_id,
            previous_state="NONE",
            new_state=SessionStatus.NEW.value,
            reason="Session created"
        )
        
        return session

    def get_session(self, session_id: str) -> Optional[SessionState]:
        """Retrieves session from memory or persistent store."""
        with self._lock:
            if session_id in self._sessions:
                return self._sessions[session_id]
                
        # Fallback to persistent storage
        loaded = self.load_session(session_id)
        if loaded:
            with self._lock:
                self._sessions[session_id] = loaded
            return loaded
        return None

    def transition_state(
        self,
        session_id: str,
        new_status: SessionStatus,
        reason: str = "",
        task_id: Optional[str] = None,
        node_id: Optional[str] = None
    ) -> SessionState:
        """
        Safely transitions session to a new lifecycle state following validation rules.
        """
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session '{session_id}' not found.")
            
        with self._lock:
            old_status = session.session_status
            if new_status != old_status:
                allowed = ALLOWED_TRANSITIONS.get(old_status, set())
                if new_status not in allowed:
                    raise ValueError(f"Invalid session state transition: cannot transition from {old_status} to {new_status}")
                    
                session.session_status = new_status
                session.updated_at = datetime.datetime.now().isoformat() + "Z"
                if task_id:
                    session.active_task_id = task_id
                if node_id:
                    session.active_node_id = node_id
                    
        self.save_session(session)
        
        # Emit observability
        obs_map = {
            SessionStatus.WAITING_FOR_CLARIFICATION: "SESSION_WAITING",
            SessionStatus.PLANNING: "SESSION_RESUMED" if old_status == SessionStatus.WAITING_FOR_CLARIFICATION else "SESSION_UPDATED",
            SessionStatus.CANCELLED: "SESSION_CANCELLED",
            SessionStatus.COMPLETED: "SESSION_COMPLETED",
            SessionStatus.FAILED: "SESSION_FAILED"
        }
        ev_type = obs_map.get(new_status, "SESSION_UPDATED")
        observability_manager.emit_event(ObservabilityEvent(
            event_type=ev_type,
            metadata={
                "session_id": session_id,
                "previous_status": old_status.value,
                "new_status": new_status.value,
                "reason": reason
            }
        ))
        
        # Audit log
        self.audit_logger.log_session_event(
            session_id=session_id,
            conversation_id=session.conversation_id,
            task_id=task_id or session.active_task_id,
            node_id=node_id or session.active_node_id,
            previous_state=old_status.value,
            new_state=new_status.value,
            reason=reason
        )
        
        return session

    def update_session(self, session_id: str, **kwargs) -> SessionState:
        """Updates attributes on an active SessionState."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session '{session_id}' not found.")
            
        with self._lock:
            for key, val in kwargs.items():
                if hasattr(session, key):
                    clean_val = sanitize_session_data(val)
                    setattr(session, key, clean_val)
            session.updated_at = datetime.datetime.now().isoformat() + "Z"
            
        self.save_session(session)
        return session

    def cancel_session(self, session_id: str, reason: str = "User cancelled") -> SessionState:
        """
        Safely cancels an active session, stopping downstream executions.
        Cancellation is NEVER recorded as a success.
        Cancels all pending approvals bound to this session.
        """
        try:
            from core.approval import approval_manager as global_mgr
            mgr = self.approval_manager or global_mgr
            mgr.cancel_session_approvals(session_id, reason=reason)
        except Exception:
            pass
        return self.transition_state(session_id, SessionStatus.CANCELLED, reason=reason)

    def add_verified_result(
        self,
        session_id: str,
        node_id: str,
        agent: str,
        result: str,
        evidence: Any
    ):
        """Records only verified execution outcomes into operational session state."""
        session = self.get_session(session_id)
        if not session:
            return
            
        entry = {
            "node_id": node_id,
            "agent": agent,
            "result": sanitize_session_data(str(result)),
            "evidence": sanitize_session_data(str(evidence)),
            "timestamp": datetime.datetime.now().isoformat() + "Z"
        }
        with self._lock:
            session.recent_verified_results.append(entry)
            session.updated_at = datetime.datetime.now().isoformat() + "Z"
            
        self.save_session(session)

    def add_failure(
        self,
        session_id: str,
        node_id: str,
        agent: str,
        error: str,
        category: str = "UNKNOWN"
    ):
        """Records node failure in operational session state."""
        session = self.get_session(session_id)
        if not session:
            return
            
        entry = {
            "node_id": node_id,
            "agent": agent,
            "error": sanitize_session_data(str(error)),
            "category": category,
            "timestamp": datetime.datetime.now().isoformat() + "Z"
        }
        with self._lock:
            session.recent_failures.append(entry)
            session.updated_at = datetime.datetime.now().isoformat() + "Z"
            
        self.save_session(session)

    def save_session(self, session: SessionState) -> bool:
        """Persists session to SQLite audit/session store."""
        try:
            return self.audit_logger.save_session_state(session.model_dump())
        except Exception as e:
            print(f"[SESSION SAVE ERROR] {e}")
            return False

    def load_session(self, session_id: str) -> Optional[SessionState]:
        """Loads session from SQLite store."""
        try:
            d = self.audit_logger.load_session_state(session_id)
            if d:
                return SessionState(**d)
            return None
        except Exception as e:
            print(f"[SESSION LOAD ERROR] {e}")
            return None

    def list_active_sessions(self) -> List[SessionState]:
        """Returns all sessions currently in active / running lifecycle states."""
        with self._lock:
            return [
                s for s in self._sessions.values()
                if s.session_status in (
                    SessionStatus.NEW,
                    SessionStatus.ACTIVE,
                    SessionStatus.PLANNING,
                    SessionStatus.EXECUTING,
                    SessionStatus.RECOVERING,
                    SessionStatus.WAITING_FOR_CLARIFICATION
                )
            ]

# Global singleton session manager
session_manager = SessionManager()
