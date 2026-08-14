import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

class EnvironmentFact(BaseModel):
    """
    Evidence-backed fact about the environment.
    """
    fact: str
    value: Any
    source: str = "UNKNOWN"
    evidence: str = "UNKNOWN"
    detected_at: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())
    verified_at: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())
    status: str = "VERIFIED" # VERIFIED or UNKNOWN

class EnvironmentKnowledge(BaseModel):
    """
    Structured project/environment knowledge document.
    """
    environment_id: str
    project_root: str
    platform: str
    os: str
    architecture: str
    languages: List[EnvironmentFact] = Field(default_factory=list)
    frameworks: List[EnvironmentFact] = Field(default_factory=list)
    package_managers: List[EnvironmentFact] = Field(default_factory=list)
    dependencies: List[EnvironmentFact] = Field(default_factory=list)
    entry_points: List[EnvironmentFact] = Field(default_factory=list)
    important_directories: List[EnvironmentFact] = Field(default_factory=list)
    important_files: List[EnvironmentFact] = Field(default_factory=list)
    services: List[EnvironmentFact] = Field(default_factory=list)
    repositories: List[EnvironmentFact] = Field(default_factory=list)
    git_state: Optional[EnvironmentFact] = None
    last_scanned: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())
    scan_version: str = "1.0"

class EnvironmentQuery(BaseModel):
    """
    Structured query for the environment index.
    """
    query: str
    project_root: str
    category: Optional[str] = None
    limit: int = 10
