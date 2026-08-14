import uuid
import json
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from core.observability import observability_manager, ObservabilityEvent

class MessageType(str, Enum):
    TASK_REQUEST = "TASK_REQUEST"
    TASK_ACCEPTED = "TASK_ACCEPTED"
    TASK_PROGRESS = "TASK_PROGRESS"
    TASK_RESULT = "TASK_RESULT"
    TASK_FAILED = "TASK_FAILED"
    TASK_BLOCKED = "TASK_BLOCKED"
    TASK_NEEDS_INPUT = "TASK_NEEDS_INPUT"
    TASK_CANCELLED = "TASK_CANCELLED"
    TASK_RETRYING = "TASK_RETRYING"
    TASK_RECOVERING = "TASK_RECOVERING"
    TASK_ESCALATED = "TASK_ESCALATED"

class AgentStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"
    RETRYING = "RETRYING"
    RECOVERING = "RECOVERING"
    ESCALATED = "ESCALATED"

class AgentError(BaseModel):
    code: str
    message: str
    severity: str = "ERROR"
    recoverable: bool = False
    source: str = "unknown"
    details: Optional[Dict[str, Any]] = None

class FileOperation(str, Enum):
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"

class FileChange(BaseModel):
    path: str
    operation: FileOperation

class AgentMessage(BaseModel):
    message_id: str
    session_id: Optional[str] = None
    task_id: Optional[str] = None
    node_id: Optional[str] = None
    parent_task_id: Optional[str] = None
    sender_agent: str
    recipient_agent: str
    message_type: MessageType
    status: AgentStatus
    result: Optional[str] = None
    evidence: List[str] = Field(default_factory=list)
    errors: List[AgentError] = Field(default_factory=list)
    files_changed: List[FileChange] = Field(default_factory=list)
    recommended_next_steps: List[str] = Field(default_factory=list)
    attempt: int = 1
    recovery_action: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

class A2ADispatcher:
    """
    Central dispatcher that implements PRD Section 10.
    Wraps agent execution in structured messaging, separating LLM claims 
    from actual verification evidence stored in the Audit Log.
    """
    def __init__(self, agents_dict: Dict[str, Any], audit_logger):
        self.agents = agents_dict
        self.audit_logger = audit_logger

    def dispatch(self, message: AgentMessage) -> AgentMessage:
        """
        Dispatches a TASK_REQUEST message to the target agent and constructs a 
        TASK_RESULT/TASK_FAILED response derived from system evidence.
        """
        if message.message_type not in (MessageType.TASK_REQUEST, MessageType.TASK_RETRYING, MessageType.TASK_RECOVERING):
            raise ValueError(f"Dispatcher expects TASK_REQUEST or retry message, got {message.message_type}")
            
        target_agent = message.recipient_agent
        if target_agent == "NOT_AVAILABLE" or target_agent not in self.agents:
            return self._build_failure_response(message, "AGENT_NOT_FOUND", f"Agent {target_agent} is not available.")
            
        agent = self.agents[target_agent]
        
        # Log the request message
        self.audit_logger.log_a2a_message(message)
        self._emit_observability(message)
        
        try:
            # Execute the agent natively. The agent will internally use ExecutionGate 
            # which logs directly to the AuditLogger under message.node_id.
            result_str = agent.execute(message.result, task_id=message.node_id)
            
            # Post-execution: Construct the response message purely from Evidence (PRD Phase 5, Phase 13)
            return self._evaluate_evidence(message, result_str)
            
        except Exception as e:
            return self._build_failure_response(message, "EXECUTION_EXCEPTION", str(e))
            
    def _evaluate_evidence(self, req: AgentMessage, agent_result_string: str) -> AgentMessage:
        """
        Queries the audit log to populate evidence and determine the true status 
        independently of what the LLM string says.
        """
        events = self.audit_logger.query_events(task_id=req.node_id)
        
        evidence = []
        errors = []
        files_changed = []
        
        status = AgentStatus.COMPLETED
        msg_type = MessageType.TASK_RESULT
        
        for e in events:
            # Populate evidence
            if e.get("evidence"):
                evidence.append(f"[{e['tool']}] {e['evidence']}")
                
            # Populate files changed (if tool logged any)
            if e.get("files_changed"):
                try:
                    f_list = json.loads(e["files_changed"])
                    for f in f_list:
                        if f not in [fc.model_dump() for fc in files_changed]:
                            files_changed.append(FileChange(**f))
                except Exception:
                    pass
            
            # Populate errors
            if e.get("verification_status") == "VERIFIED_FAILURE":
                errors.append(AgentError(
                    code="VERIFIED_FAILURE",
                    message=f"Tool {e['tool']} failed verification: {e.get('error', 'Unknown error')}",
                    source="ExecutionGate"
                ))
            elif e.get("permission_status") == "DENIED":
                errors.append(AgentError(
                    code="PERMISSION_DENIED",
                    message=f"Permission denied for tool {e['tool']}",
                    source="ExecutionGate"
                ))

        # Evaluate status from the most recent tool execution event (first in list)
        if events:
            latest = events[0]
            if latest.get("permission_status") == "DENIED":
                status = AgentStatus.BLOCKED
                msg_type = MessageType.TASK_BLOCKED
            elif latest.get("verification_status") == "VERIFIED_FAILURE":
                status = AgentStatus.FAILED
                msg_type = MessageType.TASK_FAILED
            elif latest.get("verification_status") == "VERIFIED_SUCCESS":
                status = AgentStatus.COMPLETED
                msg_type = MessageType.TASK_RESULT
                errors = [] # Cleared on successful verification
            elif latest.get("verification_status") == "UNVERIFIED":
                status = AgentStatus.FAILED
                msg_type = MessageType.TASK_FAILED
                errors.append(AgentError(
                    code="UNVERIFIED",
                    message="Tool returned UNVERIFIED status.",
                    source="ExecutionGate"
                ))

        response_msg = AgentMessage(
            message_id=str(uuid.uuid4()),
            task_id=req.task_id,
            node_id=req.node_id,
            parent_task_id=req.parent_task_id,
            sender_agent=req.recipient_agent,
            recipient_agent=req.sender_agent,
            message_type=msg_type,
            status=status,
            result=agent_result_string,
            evidence=evidence,
            errors=errors,
            files_changed=files_changed
        )
        
        self.audit_logger.log_a2a_message(response_msg)
        self._emit_observability(response_msg)
        return response_msg
        
    def _build_failure_response(self, req: AgentMessage, code: str, msg: str) -> AgentMessage:
        err = AgentError(code=code, message=msg, source="A2ADispatcher")
        resp = AgentMessage(
            message_id=str(uuid.uuid4()),
            task_id=req.task_id,
            node_id=req.node_id,
            parent_task_id=req.parent_task_id,
            sender_agent=req.recipient_agent,
            recipient_agent=req.sender_agent,
            message_type=MessageType.TASK_FAILED,
            status=AgentStatus.FAILED,
            errors=[err]
        )
        self.audit_logger.log_a2a_message(resp)
        self._emit_observability(resp)
        return resp
        
    def _emit_observability(self, message: AgentMessage):
        observability_manager.emit_event(ObservabilityEvent(
            task_id=message.task_id,
            event_type="A2A_MESSAGE",
            agent=message.sender_agent,
            metadata={
                "message_type": message.message_type.value,
                "recipient": message.recipient_agent,
                "node_id": message.node_id,
                "status": message.status.value
            }
        ))
