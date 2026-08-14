from enum import Enum
import json

class VerificationStatus(str, Enum):
    VERIFIED_SUCCESS = "VERIFIED_SUCCESS"
    VERIFIED_FAILURE = "VERIFIED_FAILURE"
    UNVERIFIED = "UNVERIFIED"

class ToolResult:
    """
    Standardized return object for all tool executions to enforce the 
    Verification-First architecture (PRD Section 49).
    """
    def __init__(self, status: VerificationStatus, message: str, evidence: str = "No evidence provided.", files_changed: list = None):
        self.status = status
        self.message = message
        self.evidence = evidence
        self.files_changed = files_changed or []

    def to_dict(self):
        return {
            "status": self.status.value,
            "message": self.message,
            "evidence": self.evidence,
            "files_changed": self.files_changed
        }

    def to_json(self):
        return json.dumps(self.to_dict())

    def __str__(self):
        return self.to_json()
