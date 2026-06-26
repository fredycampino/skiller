from dataclasses import dataclass

from skiller.application.agent.config.step_config_reader import AgentRunnerConfig
from skiller.domain.agent.llm.model import LLMModelLike, LLMResponse, LLMUsage
from skiller.domain.agent.run.identity import AgentRun
from skiller.domain.agent.run.model import AgentStopReason
from skiller.domain.tool.tool_execution_model import ToolExecutionResults


@dataclass
class AgentRunnerState:
    final_text: str | None = None
    finish: AgentStopReason | None = None
    response_model: LLMModelLike | None = None
    usage: LLMUsage | None = None
    error: str | None = None
    tool_call_count: int = 0

    def record_tool_execution(self, results: ToolExecutionResults) -> None:
        self.tool_call_count += results.executed_count()
        if results.is_interrupted():
            self.finish_interrupted()
            return
        if results.has_exception():
            self.fail_tool_execution(results.exception_message())
            return
        if not results.items:
            self.finish = AgentStopReason.FINAL

    def record_llm_response(self, response: LLMResponse) -> None:
        self.response_model = response.model
        self.usage = response.usage

    def fail_llm_request(self, error: str) -> None:
        self.finish = AgentStopReason.LLM_REQUEST_FAILED
        self.error = error

    def fail_tool_execution(self, error: str) -> None:
        self.finish = AgentStopReason.TOOL_EXECUTION_FAILED
        self.error = error

    def fail_invalid_final_message(self, error: str) -> None:
        self.finish = AgentStopReason.INVALID_FINAL_MESSAGE
        self.error = error

    def finish_final(self, final_text: str) -> None:
        self.final_text = final_text
        self.finish = AgentStopReason.FINAL

    def finish_interrupted(self) -> None:
        self.finish = AgentStopReason.INTERRUPTED

    def finish_max_turns_exhausted(self) -> None:
        self.finish = AgentStopReason.MAX_TURNS_EXHAUSTED


@dataclass(frozen=True)
class AgentRunnerRequest:
    agent: AgentRun
    config: AgentRunnerConfig


@dataclass(frozen=True)
class AgentRunnerResult:
    context_id: str
    final_text: str | None
    turn_count: int
    tool_call_count: int
    finish: AgentStopReason
    response_model: LLMModelLike | None
    usage: LLMUsage | None
    error: str | None = None
