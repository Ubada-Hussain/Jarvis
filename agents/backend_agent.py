from typing import List, Set
from agents.base_agent import BaseAgent
from agents.capabilities import AgentCapability, BACKEND_CAPABILITIES, AgentCapabilityContract
from core.verification import ToolResult, VerificationStatus
from core.execution_gate import ToolMetadata, RiskLevel
from core.dev_tools import (
    read_code_file, write_code_file, inspect_code_directory,
    run_backend_tests, run_backend_command,
    READ_CODE_FILE_TOOL, WRITE_CODE_FILE_TOOL, INSPECT_CODE_DIR_TOOL,
    RUN_BACKEND_TESTS_TOOL, RUN_BACKEND_COMMAND_TOOL
)
from core.system_tools import (
    QUERY_ENV_TOOL, REFRESH_ENV_TOOL, query_environment_index, refresh_environment_index
)
from core.tools import (
    SEARCH_INTERNET_TOOL, search_internet, OPEN_URL_TOOL, open_url
)

class BackendAgent(BaseAgent):
    name = "BackendAgent"
    description = (
        "Specialized in backend development, API endpoints, backend services, "
        "database integration, backend configurations, and backend unit testing."
    )
    capabilities: Set[AgentCapability] = BACKEND_CAPABILITIES

    def get_contract(self) -> AgentCapabilityContract:
        return AgentCapabilityContract(
            agent_name=self.name,
            capabilities=list(self.capabilities),
            description=self.description
        )

    def _setup_execution_gate(self, task_id: str = None):
        gate = super()._setup_execution_gate(task_id)
        
        # Register backend-specific and shared dev tools
        gate.register(ToolMetadata("read_code_file", RiskLevel.READ_ONLY, "fs_read"), read_code_file)
        gate.register(ToolMetadata("write_code_file", RiskLevel.REVERSIBLE, "fs_write"), write_code_file)
        gate.register(ToolMetadata("inspect_directory", RiskLevel.READ_ONLY, "fs_read"), inspect_code_directory)
        gate.register(ToolMetadata("run_backend_tests", RiskLevel.READ_ONLY, "process_execution"), run_backend_tests)
        gate.register(ToolMetadata("run_backend_command", RiskLevel.REVERSIBLE, "process_execution"), run_backend_command)
        
        return gate

    def execute(self, task: str, task_id: str = None) -> str:
        print(f"\n[{self.name}] Analyzing backend development task...")
        
        gate = self._setup_execution_gate(task_id)
        
        system_prompt = (
            f"You are {self.name}. {self.description}\n"
            "You handle backend architecture, API endpoints, databases, servers, backend tests, and configurations.\n"
            "Always use your tools to inspect, write, test, and verify backend code.\n"
            "Never claim files were created or tests passed without actually executing the verification tools.\n"
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
            RUN_BACKEND_TESTS_TOOL,
            RUN_BACKEND_COMMAND_TOOL,
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
