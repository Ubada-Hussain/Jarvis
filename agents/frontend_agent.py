from typing import List, Set
from agents.base_agent import BaseAgent
from agents.capabilities import AgentCapability, FRONTEND_CAPABILITIES, AgentCapabilityContract
from core.verification import ToolResult, VerificationStatus
from core.execution_gate import ToolMetadata, RiskLevel
from core.dev_tools import (
    read_code_file, write_code_file, inspect_code_directory,
    start_frontend_server, stop_frontend_server, frontend_server_status, run_frontend_build,
    READ_CODE_FILE_TOOL, WRITE_CODE_FILE_TOOL, INSPECT_CODE_DIR_TOOL,
    START_FRONTEND_SERVER_TOOL, STOP_FRONTEND_SERVER_TOOL,
    FRONTEND_SERVER_STATUS_TOOL, RUN_FRONTEND_BUILD_TOOL
)
from core.system_tools import (
    QUERY_ENV_TOOL, REFRESH_ENV_TOOL, query_environment_index, refresh_environment_index
)
from core.tools import (
    SEARCH_INTERNET_TOOL, search_internet, OPEN_URL_TOOL, open_url
)

class FrontendAgent(BaseAgent):
    name = "FrontendAgent"
    description = (
        "Specialized in UI components, client-side logic, styling (CSS/Tailwind), "
        "frontend state, routing, frontend build/tests, and managing the frontend dev server."
    )
    capabilities: Set[AgentCapability] = FRONTEND_CAPABILITIES

    def get_contract(self) -> AgentCapabilityContract:
        return AgentCapabilityContract(
            agent_name=self.name,
            capabilities=list(self.capabilities),
            description=self.description
        )

    def _setup_execution_gate(self, task_id: str = None):
        gate = super()._setup_execution_gate(task_id)
        
        # Register frontend-specific and shared dev tools
        gate.register(ToolMetadata("read_code_file", RiskLevel.READ_ONLY, "fs_read"), read_code_file)
        gate.register(ToolMetadata("write_code_file", RiskLevel.REVERSIBLE, "fs_write"), write_code_file)
        gate.register(ToolMetadata("inspect_directory", RiskLevel.READ_ONLY, "fs_read"), inspect_code_directory)
        gate.register(ToolMetadata("start_frontend_server", RiskLevel.REVERSIBLE, "server_execution"), start_frontend_server)
        gate.register(ToolMetadata("stop_frontend_server", RiskLevel.REVERSIBLE, "server_execution"), stop_frontend_server)
        gate.register(ToolMetadata("frontend_server_status", RiskLevel.READ_ONLY, "process_monitoring"), frontend_server_status)
        gate.register(ToolMetadata("run_frontend_build", RiskLevel.READ_ONLY, "process_execution"), run_frontend_build)
        
        # Legacy aliases for backward-compatibility with start_server / stop_server / server_status
        gate.register(ToolMetadata("start_server", RiskLevel.REVERSIBLE, "server_execution"), start_frontend_server)
        gate.register(ToolMetadata("stop_server", RiskLevel.REVERSIBLE, "server_execution"), stop_frontend_server)
        gate.register(ToolMetadata("server_status", RiskLevel.READ_ONLY, "process_monitoring"), frontend_server_status)
        
        return gate

    def execute(self, task: str, task_id: str = None) -> str:
        print(f"\n[{self.name}] Analyzing frontend development task...")
        
        gate = self._setup_execution_gate(task_id)
        
        system_prompt = (
            f"You are {self.name}. {self.description}\n"
            "You handle user interface components, styles, frontend builds, frontend tests, and frontend dev servers.\n"
            "Always use your tools to inspect, write, build, and verify UI code.\n"
            "Never claim files were created or UI servers were started without actually executing the verification tools.\n"
            "Keep responses crisp, confident, and professional."
        )

        try:
            relevant_chunks = self.memory.get_relevant_context(task, max_results=3)
            if relevant_chunks:
                system_prompt += "\n\n<MEMORY_CONTEXT>\n"
                for chunk in relevant_chunks:
                    system_prompt += f"- {chunk}\n"
                system_prompt += "</MEMORY_CONTEXT>\n"
        except Exception as e:
            print(f"[RAG WARNING] Failed to retrieve context: {e}")

        tools = [
            READ_CODE_FILE_TOOL,
            WRITE_CODE_FILE_TOOL,
            INSPECT_CODE_DIR_TOOL,
            START_FRONTEND_SERVER_TOOL,
            STOP_FRONTEND_SERVER_TOOL,
            FRONTEND_SERVER_STATUS_TOOL,
            RUN_FRONTEND_BUILD_TOOL,
            QUERY_ENV_TOOL,
            REFRESH_ENV_TOOL,
            SEARCH_INTERNET_TOOL,
            OPEN_URL_TOOL
        ]

        response = self.llm.generate_response(
            prompt=task,
            system_prompt=system_prompt,
            tools=tools,
            tool_logic=gate
        )

        if not response:
            return f"[{self.name} ERROR]: Failed to generate response."

        self.memory.save_interaction(
            user_input=task,
            ai_response=response,
            activity_type=f"agent_execution_{self.name}"
        )
        return response
