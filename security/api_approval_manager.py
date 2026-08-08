import threading
import time

class APIApprovalManager:
    """
    Manages approval requests via API.
    Used by agents to pause execution and wait for the frontend to confirm an action.
    """
    def __init__(self):
        self._pending_action = None
        self._wait_event = threading.Event()
        self._approval_result = False
        self._lock = threading.Lock()

    def require_approval(self, action_description: str, timeout_seconds: int = 30) -> bool:
        """
        Pauses execution to ask for human approval via the API.
        Returns True if approved, False otherwise.
        """
        with self._lock:
            if self._pending_action is not None:
                print(f"[APIApprovalManager] Warning: Overwriting existing pending action: {self._pending_action}")
            
            self._pending_action = action_description
            self._approval_result = False
            self._wait_event.clear()

        print(f"\n[APIApprovalManager] 🔴 CRITICAL ACTION PAUSED. Waiting for user approval: {action_description}")
        
        # Block the current thread (agent thread) until frontend responds or timeout
        signaled = self._wait_event.wait(timeout=timeout_seconds)
        
        with self._lock:
            self._pending_action = None # Clear it whether success or timeout
            
        if not signaled:
            print(f"[APIApprovalManager] ❌ Action aborted due to timeout ({timeout_seconds}s).")
            return False
            
        if self._approval_result:
            print(f"[APIApprovalManager] ✅ Action APPROVED by user.")
            return True
        else:
            print(f"[APIApprovalManager] ❌ Action REJECTED by user.")
            return False

    def get_pending_action(self) -> str | None:
        """Returns the description of the currently pending action, or None."""
        with self._lock:
            return self._pending_action

    def respond(self, approved: bool):
        """
        Called by the API endpoint to respond to the pending action.
        """
        with self._lock:
            if self._pending_action is None:
                return # Nothing to approve
            self._approval_result = approved
            self._wait_event.set()
