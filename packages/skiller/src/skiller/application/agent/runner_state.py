from dataclasses import dataclass

from skiller.application.agent.config.step_config_reader import AgentStepConfig
from skiller.domain.agent.agent_run_model import AgentRunnerFinish
from skiller.domain.agent.llm_model import LLMResponse
from skiller.domain.tool.tool_contract import ToolConfig
from skiller.domain.tool.tool_execution_model import ToolExecutionResults


@dataclass
class AgentRunnerState:
    run_id: str
    agent_id: str
    context_id: str
    config: AgentStepConfig
    enabled_tools: list[ToolConfig]
    final_text: str | None = None
    finish: AgentRunnerFinish | None = None
    response_model: str | None = None
    error: str | None = None
    tool_call_count: int = 0

    @property
    def tools_enabled(self) -> bool:
        return bool(self.config.tools)

    def record_tool_execution(self, results: ToolExecutionResults) -> None:
        self.tool_call_count += results.executed_count()
        if results.is_interrupted():
            self.finish_interrupted()
            return
        if results.has_exception():
            self.fail_tool_execution(results.exception_message())
            return
        if not results.items:
            self.finish = AgentRunnerFinish.FINAL

    def record_llm_response(self, response: LLMResponse) -> None:
        self.response_model = response.model

    def fail_llm_request(self, error: str) -> None:
        self.finish = AgentRunnerFinish.LLM_REQUEST_FAILED
        self.error = error

    def fail_tool_execution(self, error: str) -> None:
        self.finish = AgentRunnerFinish.TOOL_EXECUTION_FAILED
        self.error = error

    def fail_invalid_final_message(self, error: str) -> None:
        self.finish = AgentRunnerFinish.INVALID_FINAL_MESSAGE
        self.error = error

    def finish_final(self, final_text: str) -> None:
        self.final_text = final_text
        self.finish = AgentRunnerFinish.FINAL

    def finish_interrupted(self) -> None:
        self.finish = AgentRunnerFinish.INTERRUPTED

    def finish_max_turns_exhausted(self) -> None:
        self.finish = AgentRunnerFinish.MAX_TURNS_EXHAUSTED


@dataclass(frozen=True)
class AgentRunnerRequest:
    run_id: str
    step_id: str
    config: AgentStepConfig


@dataclass(frozen=True)
class AgentRunnerResult:
    final_text: str | None
    turn_count: int
    tool_call_count: int
    finish: AgentRunnerFinish
    response_model: str | None
    error: str | None = None
