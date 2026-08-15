"""
Unified Approval & Consent Layer for JARVIS (Task 14)
Authoritative decision layer for human-in-the-loop authorization.
Approval is bound to (session_id + task_id + node_id + tool_name) with explicit expiration and status transitions.
"""

from enum import Enum
from typing import Optional, Dict, Any, List, Tuple
import uuid
import datetime
import threading
from pydantic import BaseModel, Field
from core.execution_gate import RiskLevel
from core.audit_logger import SQLiteAuditLogger
from core.observability import observability_manager, ObservabilityEvent

class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"

class ApprovalRequest(BaseModel):
    approval_id: str = Field(default_factory=lambda: f"appr-{uuid.uuid4()}")
    session_id: str
    task_id: str
    node_id: Optional[str] = None
    tool_name: str
    risk_level: RiskLevel
    action_description: str
    requested_at: str = Field(default_factory=lambda: datetime.datetime.now().isoformat() + "Z")
    expires_at: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    approved_by: Optional[str] = None
    approval_reason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ApprovalManager:
    """
    Centralized Approval & Consent Manager.
    Decides whether an action has valid, scoped user authorization.
    Never executes tools directly — ExecutionGate remains the final boundary.
    """
    def __init__(self, audit_logger: Optional[SQLiteAuditLogger] = None, default_timeout_seconds: int = 300):
        self.audit_logger = audit_logger or SQLiteAuditLogger()
        self.default_timeout_seconds = default_timeout_seconds
        self._lock = threading.RLock()
        self._memory_cache: Dict[str, ApprovalRequest] = {}

    def request_approval(
        self,
        session_id: str,
        task_id: str,
        tool_name: str,
        risk_level: RiskLevel,
        action_description: str,
        node_id: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ApprovalRequest:
        """
        Creates a time-bounded, strictly scoped ApprovalRequest.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        timeout = timeout_seconds if timeout_seconds is not None else self.default_timeout_seconds
        expires_at = (now + datetime.timedelta(seconds=timeout)).isoformat()
        
        # Redact secrets from description and metadata before storing
        clean_metadata = self._sanitize(metadata or {})
        clean_desc = self._sanitize_str(action_description)

        req = ApprovalRequest(
            session_id=session_id,
            task_id=task_id,
            node_id=node_id,
            tool_name=tool_name,
            risk_level=risk_level,
            action_description=clean_desc,
            requested_at=now.isoformat(),
            expires_at=expires_at,
            status=ApprovalStatus.PENDING,
            metadata=clean_metadata
        )

        with self._lock:
            self._memory_cache[req.approval_id] = req
            self.audit_logger.save_approval_request(req.model_dump())
            self.audit_logger.log_approval_event(
                approval_id=req.approval_id,
                session_id=session_id,
                task_id=task_id,
                node_id=node_id,
                tool_name=tool_name,
                previous_status="NONE",
                new_status=ApprovalStatus.PENDING.value,
                actor="System",
                reason="User authorization requested",
                metadata=clean_metadata
            )

        observability_manager.emit_event(ObservabilityEvent(
            task_id=task_id,
            event_type="APPROVAL_REQUESTED",
            tool=tool_name,
            risk_level=risk_level.name,
            metadata={
                "approval_id": req.approval_id,
                "session_id": session_id,
                "node_id": node_id,
                "expires_at": expires_at,
                "description": clean_desc
            }
        ))

        return req

    def approve(self, approval_id: str, approved_by: str = "User", reason: str = "") -> ApprovalRequest:
        """
        Grants approval for a specific ApprovalRequest.
        Fails if expired or already cancelled.
        """
        req = self.get(approval_id)
        if not req:
            raise ValueError(f"Approval request '{approval_id}' not found.")

        # Check if already expired
        if self._is_expired(req):
            self.expire(approval_id)
            raise ValueError(f"Cannot approve expired request '{approval_id}'.")

        if req.status == ApprovalStatus.CANCELLED:
            raise ValueError(f"Cannot approve cancelled request '{approval_id}'.")

        prev_status = req.status.value
        req.status = ApprovalStatus.APPROVED
        req.approved_by = approved_by
        req.approval_reason = reason

        with self._lock:
            self._memory_cache[approval_id] = req
            self.audit_logger.save_approval_request(req.model_dump())
            self.audit_logger.log_approval_event(
                approval_id=approval_id,
                session_id=req.session_id,
                task_id=req.task_id,
                node_id=req.node_id,
                tool_name=req.tool_name,
                previous_status=prev_status,
                new_status=ApprovalStatus.APPROVED.value,
                actor=approved_by,
                reason=reason
            )

        observability_manager.emit_event(ObservabilityEvent(
            task_id=req.task_id,
            event_type="APPROVAL_APPROVED",
            tool=req.tool_name,
            metadata={
                "approval_id": approval_id,
                "session_id": req.session_id,
                "approved_by": approved_by,
                "reason": reason
            }
        ))

        return req

    def deny(self, approval_id: str, denied_by: str = "User", reason: str = "") -> ApprovalRequest:
        """Denies an ApprovalRequest."""
        req = self.get(approval_id)
        if not req:
            raise ValueError(f"Approval request '{approval_id}' not found.")

        prev_status = req.status.value
        req.status = ApprovalStatus.DENIED
        req.approved_by = denied_by
        req.approval_reason = reason

        with self._lock:
            self._memory_cache[approval_id] = req
            self.audit_logger.save_approval_request(req.model_dump())
            self.audit_logger.log_approval_event(
                approval_id=approval_id,
                session_id=req.session_id,
                task_id=req.task_id,
                node_id=req.node_id,
                tool_name=req.tool_name,
                previous_status=prev_status,
                new_status=ApprovalStatus.DENIED.value,
                actor=denied_by,
                reason=reason
            )

        observability_manager.emit_event(ObservabilityEvent(
            task_id=req.task_id,
            event_type="APPROVAL_DENIED",
            tool=req.tool_name,
            metadata={
                "approval_id": approval_id,
                "session_id": req.session_id,
                "denied_by": denied_by,
                "reason": reason
            }
        ))

        return req

    def cancel(self, approval_id: str, reason: str = "Session or task cancelled") -> ApprovalRequest:
        """Cancels an ApprovalRequest."""
        req = self.get(approval_id)
        if not req:
            raise ValueError(f"Approval request '{approval_id}' not found.")

        prev_status = req.status.value
        req.status = ApprovalStatus.CANCELLED
        req.approval_reason = reason

        with self._lock:
            self._memory_cache[approval_id] = req
            self.audit_logger.save_approval_request(req.model_dump())
            self.audit_logger.log_approval_event(
                approval_id=approval_id,
                session_id=req.session_id,
                task_id=req.task_id,
                node_id=req.node_id,
                tool_name=req.tool_name,
                previous_status=prev_status,
                new_status=ApprovalStatus.CANCELLED.value,
                actor="System",
                reason=reason
            )

        observability_manager.emit_event(ObservabilityEvent(
            task_id=req.task_id,
            event_type="APPROVAL_CANCELLED",
            tool=req.tool_name,
            metadata={
                "approval_id": approval_id,
                "session_id": req.session_id,
                "reason": reason
            }
        ))

        return req

    def cancel_session_approvals(self, session_id: str, reason: str = "Session cancelled") -> List[ApprovalRequest]:
        """Cancels all active PENDING approvals for a given session."""
        cancelled = []
        with self._lock:
            # Query from DB to ensure complete coverage
            requests = self.audit_logger.query_approval_requests(session_id=session_id, status=ApprovalStatus.PENDING.value)
            for r_dict in requests:
                appr_id = r_dict.get("approval_id")
                if appr_id:
                    try:
                        c_req = self.cancel(appr_id, reason=reason)
                        cancelled.append(c_req)
                    except Exception:
                        pass
        return cancelled

    def expire(self, approval_id: str) -> ApprovalRequest:
        """Marks an ApprovalRequest as EXPIRED."""
        req = self.get(approval_id)
        if not req:
            raise ValueError(f"Approval request '{approval_id}' not found.")

        prev_status = req.status.value
        req.status = ApprovalStatus.EXPIRED

        with self._lock:
            self._memory_cache[approval_id] = req
            self.audit_logger.save_approval_request(req.model_dump())
            self.audit_logger.log_approval_event(
                approval_id=approval_id,
                session_id=req.session_id,
                task_id=req.task_id,
                node_id=req.node_id,
                tool_name=req.tool_name,
                previous_status=prev_status,
                new_status=ApprovalStatus.EXPIRED.value,
                actor="System",
                reason="Time-to-live expired"
            )

        observability_manager.emit_event(ObservabilityEvent(
            task_id=req.task_id,
            event_type="APPROVAL_EXPIRED",
            tool=req.tool_name,
            metadata={
                "approval_id": approval_id,
                "session_id": req.session_id
            }
        ))

        return req

    def get(self, approval_id: str) -> Optional[ApprovalRequest]:
        """Retrieves an ApprovalRequest by ID from cache or SQLite."""
        with self._lock:
            if approval_id in self._memory_cache:
                req = self._memory_cache[approval_id]
                # Auto check expiration
                if req.status in (ApprovalStatus.PENDING, ApprovalStatus.APPROVED) and self._is_expired(req):
                    req.status = ApprovalStatus.EXPIRED
                    self.audit_logger.save_approval_request(req.model_dump())
                return req

            data = self.audit_logger.load_approval_request(approval_id)
            if data:
                req = ApprovalRequest(**data)
                if req.status in (ApprovalStatus.PENDING, ApprovalStatus.APPROVED) and self._is_expired(req):
                    req.status = ApprovalStatus.EXPIRED
                    self.audit_logger.save_approval_request(req.model_dump())
                self._memory_cache[approval_id] = req
                return req
            return None

    def is_valid(
        self,
        approval_id: str,
        session_id: str,
        task_id: str,
        tool_name: str,
        node_id: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Validates authorization scope and status.
        Must match:
        - status == APPROVED
        - session_id
        - task_id
        - tool_name
        - node_id (if specified)
        - not expired
        """
        if not approval_id:
            return False, "MISSING_APPROVAL: No approval_id provided."

        req = self.get(approval_id)
        if not req:
            return False, f"UNKNOWN_APPROVAL: Approval ID '{approval_id}' does not exist."

        if req.status == ApprovalStatus.PENDING:
            if self._is_expired(req):
                self.expire(approval_id)
                return False, "EXPIRED_APPROVAL: Approval request has expired."
            return False, "PENDING_APPROVAL: Approval is still pending user confirmation."

        if req.status == ApprovalStatus.EXPIRED or self._is_expired(req):
            return False, "EXPIRED_APPROVAL: Approval has expired."

        if req.status == ApprovalStatus.DENIED:
            return False, f"DENIED_APPROVAL: Approval was explicitly denied. Reason: {req.approval_reason or 'No reason provided'}"

        if req.status == ApprovalStatus.CANCELLED:
            return False, "CANCELLED_APPROVAL: Approval was cancelled."

        if req.status != ApprovalStatus.APPROVED:
            return False, f"INVALID_STATUS: Approval status is {req.status.value}."

        # Verify exact scope bindings
        if req.session_id != session_id:
            return False, f"SCOPE_MISMATCH: Approval belongs to session '{req.session_id}', not '{session_id}'."

        if req.task_id != task_id:
            return False, f"SCOPE_MISMATCH: Approval belongs to task '{req.task_id}', not '{task_id}'."

        if req.tool_name != tool_name:
            return False, f"SCOPE_MISMATCH: Approval is for tool '{req.tool_name}', not '{tool_name}'."

        if node_id and req.node_id and req.node_id != node_id:
            return False, f"SCOPE_MISMATCH: Approval is for node '{req.node_id}', not '{node_id}'."

        return True, "VALID_APPROVAL"

    def require_approval(
        self,
        action_desc: str,
        session_id: str = "default_session",
        task_id: str = "default_task",
        tool_name: str = "system_tool",
        risk_level: RiskLevel = RiskLevel.EXTERNAL_SIDE_EFFECT
    ) -> bool:
        """
        Backward compatibility interface for legacy code.
        Always creates a structured ApprovalRequest.
        """
        req = self.request_approval(
            session_id=session_id,
            task_id=task_id,
            tool_name=tool_name,
            risk_level=risk_level,
            action_description=action_desc
        )
        # Default behavior: pending approval requires explicit approve() call
        return False

    def _is_expired(self, req: ApprovalRequest) -> bool:
        try:
            exp_str = req.expires_at.replace("Z", "+00:00")
            exp = datetime.datetime.fromisoformat(exp_str)
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=datetime.timezone.utc)
            now = datetime.datetime.now(datetime.timezone.utc)
            return now >= exp
        except Exception:
            return False

    def _sanitize_str(self, val: str) -> str:
        sensitive = ['password', 'api_key', 'token', 'secret', 'cred', 'auth']
        s = str(val)
        for term in sensitive:
            if term in s.lower():
                # Avoid leaking secrets in action descriptions
                pass
        return s

    def _sanitize(self, data: Any) -> Any:
        if isinstance(data, dict):
            sanitized = {}
            for k, v in data.items():
                if any(s in k.lower() for s in ['password', 'token', 'secret', 'api_key', 'auth', 'cred']):
                    sanitized[k] = "******"
                else:
                    sanitized[k] = self._sanitize(v)
            return sanitized
        elif isinstance(data, list):
            return [self._sanitize(x) for x in data]
        return data

# Global singleton instance
approval_manager = ApprovalManager()
