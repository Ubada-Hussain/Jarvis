import time
import uuid
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict, field

@dataclass
class ObservabilityEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    task_id: Optional[str] = None
    event_type: str = "UNKNOWN"
    agent: Optional[str] = None
    tool: Optional[str] = None
    status: Optional[str] = None
    duration_ms: Optional[int] = None
    model: Optional[str] = None
    risk_level: Optional[str] = None
    permission_status: Optional[str] = None
    verification_status: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class ObservabilityManager:
    """
    Manages live runtime state and event broadcasting for Developer Mode.
    Singleton pattern so it can be accessed globally by ExecutionGate and LLMEngine.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ObservabilityManager, cls).__new__(cls)
                cls._instance._init_state()
        return cls._instance

    def _init_state(self):
        self.callbacks = []
        self.active_task_id = None
        self.runtime_state = {
            "task_id": None,
            "user_request": "",
            "status": "IDLE",
            "current_step": "",
            "active_agent": None,
            "active_tool": None,
            "started_at": None,
            "elapsed_time": 0,
            "model": "UNKNOWN",
            "risk_level": None,
            "permission_status": None,
            "verification_status": None,
            "last_error": None
        }
        self.events_history = []
        self.task_start_time = None

    def register_callback(self, callback):
        """Register a callback (e.g., websocket broadcaster)"""
        if callback not in self.callbacks:
            self.callbacks.append(callback)

    def unregister_callback(self, callback):
        if callback in self.callbacks:
            self.callbacks.remove(callback)

    def _broadcast(self, event: ObservabilityEvent):
        """Sends event and current state to all subscribers."""
        if self.task_start_time and self.runtime_state["status"] not in ["IDLE", "COMPLETED", "FAILED"]:
            self.runtime_state["elapsed_time"] = int((time.time() - self.task_start_time) * 1000)
            
        payload = {
            "type": "observability_update",
            "state": self.runtime_state,
            "event": asdict(event)
        }
        for cb in self.callbacks:
            try:
                cb(payload)
            except Exception as e:
                print(f"[OBSERVABILITY ERROR] Callback failed: {e}")

    def emit_event(self, event: ObservabilityEvent):
        """Records an event and broadcasts it."""
        if not event.task_id:
            event.task_id = self.active_task_id
            
        self.events_history.append(event)
        # Keep history bounded for memory safety
        if len(self.events_history) > 1000:
            self.events_history.pop(0)
            
        self._broadcast(event)

    def start_task(self, task_id: str, user_request: str):
        self.active_task_id = task_id
        self.task_start_time = time.time()
        self.runtime_state.update({
            "task_id": task_id,
            "user_request": user_request,
            "status": "PLANNING",
            "current_step": "Analyzing task",
            "active_agent": "MasterAgent",
            "active_tool": None,
            "started_at": datetime.utcnow().isoformat() + "Z",
            "elapsed_time": 0,
            "last_error": None
        })
        self.emit_event(ObservabilityEvent(
            task_id=task_id, 
            event_type="TASK_STARTED", 
            agent="MasterAgent", 
            metadata={"request": user_request}
        ))

    def end_task(self, status: str = "COMPLETED", error: str = None):
        if self.task_start_time:
            self.runtime_state["elapsed_time"] = int((time.time() - self.task_start_time) * 1000)
        self.runtime_state["status"] = status
        self.runtime_state["active_agent"] = None
        self.runtime_state["active_tool"] = None
        if error:
            self.runtime_state["last_error"] = error
            
        self.emit_event(ObservabilityEvent(
            task_id=self.active_task_id,
            event_type="TASK_FAILED" if status == "FAILED" else "TASK_COMPLETED",
            status=status,
            error=error
        ))
        # Don't clear active_task_id immediately so UI can display final state

    def update_agent(self, agent: str):
        self.runtime_state["active_agent"] = agent
        self.runtime_state["status"] = "EXECUTING"
        self.emit_event(ObservabilityEvent(
            task_id=self.active_task_id,
            event_type="AGENT_SELECTED",
            agent=agent
        ))

    def get_current_state(self):
        if self.task_start_time and self.runtime_state["status"] not in ["IDLE", "COMPLETED", "FAILED"]:
            self.runtime_state["elapsed_time"] = int((time.time() - self.task_start_time) * 1000)
        return self.runtime_state

# Global singleton instance
observability_manager = ObservabilityManager()
