from enum import Enum
from typing import Set, List, Dict, Any
from pydantic import BaseModel, Field

class AgentCapability(str, Enum):
    # Backend Capabilities
    BACKEND_CODE = "backend_code"
    API = "api"
    SERVER = "server"
    DATABASE = "database"
    BACKEND_TESTS = "backend_tests"
    BACKEND_DEPENDENCIES = "backend_dependencies"

    # Frontend Capabilities
    FRONTEND_CODE = "frontend_code"
    COMPONENTS = "components"
    STYLING = "styling"
    FRONTEND_BUILD = "frontend_build"
    FRONTEND_TESTS = "frontend_tests"
    FRONTEND_DEPENDENCIES = "frontend_dependencies"

    # Shared / Common Capabilities
    CODE_READING = "code_reading"
    FS_READ = "fs_read"
    FS_WRITE = "fs_write"
    ENVIRONMENT_QUERY = "environment_query"
    INTERNET_SEARCH = "internet_search"
    GIT_READ = "git_read"
    MEDIA_CONTROL = "media_control"
    SYSTEM_CONTROL = "system_control"

BACKEND_CAPABILITIES: Set[AgentCapability] = {
    AgentCapability.BACKEND_CODE,
    AgentCapability.API,
    AgentCapability.SERVER,
    AgentCapability.DATABASE,
    AgentCapability.BACKEND_TESTS,
    AgentCapability.BACKEND_DEPENDENCIES,
    AgentCapability.CODE_READING,
    AgentCapability.FS_READ,
    AgentCapability.FS_WRITE,
    AgentCapability.ENVIRONMENT_QUERY,
    AgentCapability.INTERNET_SEARCH,
    AgentCapability.GIT_READ,
}

FRONTEND_CAPABILITIES: Set[AgentCapability] = {
    AgentCapability.FRONTEND_CODE,
    AgentCapability.COMPONENTS,
    AgentCapability.STYLING,
    AgentCapability.FRONTEND_BUILD,
    AgentCapability.FRONTEND_TESTS,
    AgentCapability.FRONTEND_DEPENDENCIES,
    AgentCapability.CODE_READING,
    AgentCapability.FS_READ,
    AgentCapability.FS_WRITE,
    AgentCapability.ENVIRONMENT_QUERY,
    AgentCapability.INTERNET_SEARCH,
    AgentCapability.GIT_READ,
}

SHARED_DEV_CAPABILITIES: Set[AgentCapability] = {
    AgentCapability.CODE_READING,
    AgentCapability.FS_READ,
    AgentCapability.ENVIRONMENT_QUERY,
    AgentCapability.INTERNET_SEARCH,
    AgentCapability.GIT_READ,
}

class AgentCapabilityContract(BaseModel):
    agent_name: str
    capabilities: List[AgentCapability]
    description: str

    def has_capability(self, cap: AgentCapability) -> bool:
        return cap in self.capabilities
