import time
import math
from enum import Enum
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from pydantic import BaseModel, Field

from core.verification import VerificationStatus, ToolResult
from core.observability import observability_manager, ObservabilityEvent

class FailureCategory(str, Enum):
    TOOL_ERROR = "TOOL_ERROR"
    VERIFICATION_FAILURE = "VERIFICATION_FAILURE"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    USER_CANCELLED = "USER_CANCELLED"
    TIMEOUT = "TIMEOUT"
    AGENT_ERROR = "AGENT_ERROR"
    A2A_ERROR = "A2A_ERROR"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
    TEST_FAILURE = "TEST_FAILURE"
    BUILD_FAILURE = "BUILD_FAILURE"
    SERVER_START_FAILURE = "SERVER_START_FAILURE"
    UNKNOWN_FAILURE = "UNKNOWN_FAILURE"

class RecoveryAction(str, Enum):
    RETRY = "RETRY"
    RECOVER = "RECOVER"
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"
    FAIL = "FAIL"

class RetryPolicy(BaseModel):
    max_retries: int = 2
    backoff_factor: float = 0.5
    initial_delay_s: float = 0.2
    retryable: bool = False
    idempotent: bool = False

@dataclass
class RecoveryDecision:
    action: RecoveryAction
    category: FailureCategory
    reason: str
    retry_delay_s: float = 0.0
    attempt: int = 1
    max_retries: int = 2
    should_retry: bool = False

class RecoveryManager:
    """
    Centralized, policy-driven failure recovery engine (PRD Phase 3, Task 10).
    Classifies failures, determines recoverability, evaluates retry budgets,
    and enforces strict Verification-First rules.
    """
    
    # Strictly non-retryable categories
    NON_RETRYABLE_CATEGORIES = {
        FailureCategory.PERMISSION_DENIED,
        FailureCategory.USER_CANCELLED,
        FailureCategory.DEPENDENCY_FAILURE,
        FailureCategory.AGENT_ERROR,
    }

    # Potentially retryable categories (subject to idempotency and budget)
    RETRYABLE_CATEGORIES = {
        FailureCategory.TIMEOUT,
        FailureCategory.SERVER_START_FAILURE,
        FailureCategory.TOOL_ERROR,
        FailureCategory.A2A_ERROR,
        FailureCategory.VERIFICATION_FAILURE,
        FailureCategory.TEST_FAILURE,
        FailureCategory.BUILD_FAILURE,
    }

    def __init__(self, default_max_retries: int = 2):
        self.default_max_retries = default_max_retries

    def classify_failure(
        self,
        error_code: str = "",
        error_msg: str = "",
        verification_status: str = "",
        tool_name: str = "",
        permission_status: str = ""
    ) -> FailureCategory:
        """
        Classifies an observed failure state into the canonical FailureCategory.
        """
        err_lower = (error_msg or "").lower()
        code_upper = (error_code or "").upper()
        
        # 1. Permission & User cancellation (Highest priority)
        if permission_status == "DENIED" or "permission denied" in err_lower or "denied: user rejected" in err_lower or code_upper == "PERMISSION_DENIED":
            return FailureCategory.PERMISSION_DENIED
        if "user cancelled" in err_lower or "cancelled by user" in err_lower or code_upper == "USER_CANCELLED":
            return FailureCategory.USER_CANCELLED
            
        # 2. Timeout
        if "timeout" in err_lower or "timed out" in err_lower or code_upper == "TIMEOUT":
            return FailureCategory.TIMEOUT
            
        # 3. Server Startup
        if "server" in tool_name.lower() or "port" in err_lower or "start_server" in tool_lower(tool_name) or "server process started" in err_lower:
            return FailureCategory.SERVER_START_FAILURE
            
        # 4. Tests & Builds
        if "test" in tool_name.lower() or "backend tests failed" in err_lower:
            return FailureCategory.TEST_FAILURE
        if "build" in tool_name.lower() or "frontend build failed" in err_lower:
            return FailureCategory.BUILD_FAILURE
            
        # 5. Agent & A2A
        if "agent_not_found" in code_upper or "not available" in err_lower or "unsupported capability" in err_lower:
            return FailureCategory.AGENT_ERROR
        if "a2a" in code_upper or "dispatcher" in err_lower:
            return FailureCategory.A2A_ERROR
            
        # 6. Dependency
        if "blocked by upstream dependency" in err_lower or "dependency failed" in err_lower:
            return FailureCategory.DEPENDENCY_FAILURE
            
        # 7. Verification Failure vs Tool Crash
        if verification_status == VerificationStatus.VERIFIED_FAILURE.value or verification_status == "VERIFIED_FAILURE":
            return FailureCategory.VERIFICATION_FAILURE
        if "exception" in err_lower or "crashed" in err_lower or "error" in err_lower:
            return FailureCategory.TOOL_ERROR
            
        return FailureCategory.UNKNOWN_FAILURE

    def evaluate_recovery(
        self,
        category: FailureCategory,
        current_attempt: int,
        max_retries: int = None,
        retry_policy: Optional[RetryPolicy] = None,
        risk_level: str = "UNKNOWN",
        requires_confirmation: bool = False
    ) -> RecoveryDecision:
        """
        Evaluates whether a failed action can be retried or recovered, and calculates backoff delay.
        Strictly enforces:
          - No retries for PERMISSION_DENIED or USER_CANCELLED
          - No automatic retries for DESTRUCTIVE actions
          - Max retry budget limits
        """
        effective_max_retries = max_retries if max_retries is not None else (retry_policy.max_retries if retry_policy else self.default_max_retries)
        
        # 1. Non-retryable failure categories
        if category in self.NON_RETRYABLE_CATEGORIES:
            action = RecoveryAction.BLOCK if category == FailureCategory.DEPENDENCY_FAILURE else RecoveryAction.FAIL
            return RecoveryDecision(
                action=action,
                category=category,
                reason=f"Category '{category.value}' is non-retryable by security policy.",
                attempt=current_attempt,
                max_retries=effective_max_retries,
                should_retry=False
            )
            
        # 2. Risk check: Destructive or confirmation-gated actions cannot be retried automatically
        if risk_level in ("DESTRUCTIVE", "EXTERNAL_SIDE_EFFECT") and requires_confirmation:
            return RecoveryDecision(
                action=RecoveryAction.FAIL,
                category=category,
                reason=f"Action with RiskLevel '{risk_level}' requires explicit confirmation and cannot be automatically retried.",
                attempt=current_attempt,
                max_retries=effective_max_retries,
                should_retry=False
            )
            
        # 3. Policy retryable check
        if retry_policy and not retry_policy.retryable and not retry_policy.idempotent:
            # If explicit policy says not retryable
            return RecoveryDecision(
                action=RecoveryAction.FAIL,
                category=category,
                reason="Action declared non-retryable in RetryPolicy metadata.",
                attempt=current_attempt,
                max_retries=effective_max_retries,
                should_retry=False
            )

        # 4. Budget check
        if current_attempt >= effective_max_retries:
            return RecoveryDecision(
                action=RecoveryAction.FAIL,
                category=category,
                reason=f"Retry budget exhausted ({current_attempt}/{effective_max_retries} attempts).",
                attempt=current_attempt,
                max_retries=effective_max_retries,
                should_retry=False
            )
            
        # 5. Calculate backoff delay
        backoff_factor = retry_policy.backoff_factor if retry_policy else 0.5
        initial_delay = retry_policy.initial_delay_s if retry_policy else 0.2
        delay = initial_delay * (2 ** (current_attempt - 1)) * backoff_factor

        action = RecoveryAction.RECOVER if category == FailureCategory.SERVER_START_FAILURE else RecoveryAction.RETRY
        
        return RecoveryDecision(
            action=action,
            category=category,
            reason=f"Transient failure '{category.value}' is recoverable. Proceeding with attempt {current_attempt + 1}/{effective_max_retries}.",
            retry_delay_s=delay,
            attempt=current_attempt + 1,
            max_retries=effective_max_retries,
            should_retry=True
        )

def tool_lower(tool_name: Any) -> str:
    return str(tool_name).lower() if tool_name else ""
