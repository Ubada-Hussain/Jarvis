import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

class MemoryType(str, Enum):
    SEMANTIC = "semantic"
    EPISODIC = "episodic"
    PROCEDURAL = "procedural"

class EpisodicMemory(BaseModel):
    memory_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    task_id: str
    session_id: Optional[str] = None
    event_type: str = "TASK_COMPLETION"
    summary: str
    outcome: str
    evidence_reference: str = "None"
    agents_involved: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

class ProcedureStep(BaseModel):
    step_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent: str
    action: str
    description: str

class ProceduralMemory(BaseModel):
    procedure_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    trigger: str
    steps: List[ProcedureStep]
    dependencies: List[str] = Field(default_factory=list)
    required_capabilities: List[str] = Field(default_factory=list)
    risk_profile: str = "LOW"
    verification_requirements: List[str] = Field(default_factory=list)
    enabled: bool = True
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    last_used: Optional[str] = None
    success_count: int = 0
    failure_count: int = 0

class MemoryQuery(BaseModel):
    query: str
    memory_types: List[MemoryType] = Field(default_factory=lambda: [MemoryType.SEMANTIC, MemoryType.EPISODIC, MemoryType.PROCEDURAL])
    limit: int = 3
    filters: Optional[Dict[str, Any]] = None
