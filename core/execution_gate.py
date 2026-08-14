from enum import IntEnum
from typing import Callable, Any, Dict, Tuple
import time
import uuid
import json
from datetime import datetime
from core.verification import ToolResult, VerificationStatus
from core.audit_logger import SQLiteAuditLogger, AuditEvent
from core.observability import observability_manager, ObservabilityEvent

class RiskLevel(IntEnum):
    READ_ONLY = 0
    REVERSIBLE = 1
    EXTERNAL_SIDE_EFFECT = 2
    DESTRUCTIVE = 3

class ToolMetadata:
    def __init__(self, name: str, risk_level: RiskLevel, required_permission: str, requires_confirmation: bool = None, target_arg: str = None):
        self.name = name
        self.risk_level = risk_level
        self.required_permission = required_permission
        self.target_arg = target_arg
        
        # PRD Section 13: Level 2 normally requires confirmation. Level 3 explicitly requires it.
        if requires_confirmation is None:
            self.requires_confirmation = (self.risk_level >= RiskLevel.EXTERNAL_SIDE_EFFECT)
        else:
            self.requires_confirmation = requires_confirmation

class ExecutionGate:
    """
    Centralized Execution Gate to enforce the Permission and Risk Model.
    Tools cannot be executed by the LLM without passing through this gate.
    """
    def __init__(self, approval_manager=None, agent_name="System", task_id=None, audit_logger=None):
        self.approval_manager = approval_manager
        self.agent_name = agent_name
        self.task_id = task_id or str(uuid.uuid4())
        self.audit_logger = audit_logger or SQLiteAuditLogger()
        self._registry: Dict[str, Tuple[ToolMetadata, Callable]] = {}

    def register(self, metadata: ToolMetadata, func: Callable):
        """Registers a tool with its metadata and implementation."""
        self._registry[metadata.name] = (metadata, func)

    def _sanitize_kwargs(self, kwargs: dict) -> dict:
        """Removes passwords or API keys before logging."""
        sanitized = {}
        sensitive_keys = ['password', 'api_key', 'token', 'secret', 'cred']
        for k, v in kwargs.items():
            if any(s in k.lower() for s in sensitive_keys):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = v
        return sanitized

    def _extract_target(self, metadata: ToolMetadata, kwargs: dict) -> str:
        """Determines the 'target' of the action for the audit log."""
        if metadata.target_arg and metadata.target_arg in kwargs:
            return str(kwargs[metadata.target_arg])
        if kwargs:
            sanitized = self._sanitize_kwargs(kwargs)
            # Take the first argument as target if small enough
            first_val = str(list(sanitized.values())[0])
            return first_val if len(first_val) < 50 else "system"
        return "system"

    def execute(self, tool_name: str, **kwargs) -> ToolResult:
        """
        Executes a tool after performing risk assessment, permission checks,
        and requesting user confirmation if required. Logs EVERYTHING to Audit Log
        and Observability Manager.
        """
        start_time = time.time()
        event_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        observability_manager.runtime_state["active_tool"] = tool_name
        observability_manager.emit_event(ObservabilityEvent(
            event_type="TOOL_REQUESTED",
            tool=tool_name,
            agent=self.agent_name
        ))
        
        # Base event state
        event = AuditEvent(
            event_id=event_id, timestamp=timestamp, task_id=self.task_id,
            agent=self.agent_name, tool=tool_name, action=f"Execute {tool_name}",
            target="unknown", risk_level="UNKNOWN",
            permission_status="UNKNOWN", confirmation_status="NOT_REQUIRED",
            execution_status="NOT_EXECUTED", verification_status="NONE",
            result="", evidence="", duration_ms=0
        )

        def _finalize_audit(result_obj: ToolResult):
            duration = int((time.time() - start_time) * 1000)
            event.duration_ms = duration
            event.result = result_obj.message
            event.evidence = result_obj.evidence
            if hasattr(result_obj, 'files_changed') and result_obj.files_changed:
                event.files_changed = json.dumps(result_obj.files_changed)
            self.audit_logger.log_event(event)
            
            observability_manager.emit_event(ObservabilityEvent(
                event_type="TOOL_COMPLETED",
                tool=tool_name,
                agent=self.agent_name,
                duration_ms=duration,
                status=event.execution_status,
                permission_status=event.permission_status,
                verification_status=event.verification_status,
                error=result_obj.message if result_obj.status == VerificationStatus.VERIFIED_FAILURE else None,
                risk_level=event.risk_level
            ))
            observability_manager.runtime_state["active_tool"] = None
            return result_obj

        if tool_name not in self._registry:
            return _finalize_audit(ToolResult(
                status=VerificationStatus.VERIFIED_FAILURE,
                message=f"[{tool_name} ERROR] Tool not registered in ExecutionGate.",
                evidence="Security blocked execution: Missing metadata."
            ))
            
        metadata, func = self._registry[tool_name]
        
        event.risk_level = metadata.risk_level.name
        event.target = self._extract_target(metadata, kwargs)
        
        # --- PERMISSION & CONFIRMATION CHECK ---
        if metadata.requires_confirmation:
            event.confirmation_status = "PENDING"
            if not self.approval_manager:
                event.permission_status = "DENIED"
                event.confirmation_status = "DENIED"
                return _finalize_audit(ToolResult(
                    status=VerificationStatus.VERIFIED_FAILURE,
                    message=f"[{tool_name} ERROR] Approval required but no ApprovalManager is configured.",
                    evidence="Security blocked execution: Missing ApprovalManager for restricted tool."
                ))
            
            # Pause and ask for permission BEFORE execution
            action_desc = f"Execute tool '{tool_name}' (Risk Level {metadata.risk_level.name})"
            sanitized = self._sanitize_kwargs(kwargs)
            if sanitized:
                action_desc += f" with args: {sanitized}"
                
            observability_manager.runtime_state["status"] = "WAITING_FOR_CONFIRMATION"
            observability_manager.emit_event(ObservabilityEvent(
                event_type="CONFIRMATION_REQUIRED",
                tool=tool_name,
                agent=self.agent_name,
                risk_level=metadata.risk_level.name
            ))
            
            approved = self.approval_manager.require_approval(action_desc)
            observability_manager.runtime_state["status"] = "EXECUTING"
            
            if not approved:
                event.permission_status = "DENIED"
                event.confirmation_status = "DENIED"
                return _finalize_audit(ToolResult(
                    status=VerificationStatus.VERIFIED_FAILURE,
                    message="DENIED: User rejected the action.",
                    evidence="Execution gate blocked tool invocation."
                ))
            event.permission_status = "GRANTED"
            event.confirmation_status = "GRANTED"
        else:
            event.permission_status = "GRANTED"
                
        # --- EXECUTION ---
        event.execution_status = "EXECUTED"
        
        observability_manager.emit_event(ObservabilityEvent(
            event_type="TOOL_STARTED",
            tool=tool_name,
            agent=self.agent_name,
            risk_level=metadata.risk_level.name,
            permission_status=event.permission_status
        ))
        
        try:
            result = func(**kwargs)
            if not isinstance(result, ToolResult):
                event.verification_status = VerificationStatus.UNVERIFIED.value
                return _finalize_audit(ToolResult(
                    status=VerificationStatus.UNVERIFIED,
                    message=str(result),
                    evidence="Warning: Tool did not return a ToolResult object."
                ))
            event.verification_status = result.status.value
            return _finalize_audit(result)
        except Exception as e:
            event.verification_status = VerificationStatus.VERIFIED_FAILURE.value
            return _finalize_audit(ToolResult(
                status=VerificationStatus.VERIFIED_FAILURE,
                message=f"[{tool_name} ERROR] Tool crashed during execution: {str(e)}",
                evidence="ExecutionGate caught an unhandled exception."
            ))
