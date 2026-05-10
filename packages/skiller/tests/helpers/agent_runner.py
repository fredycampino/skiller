from __future__ import annotations

from skiller.application.agent.agent_runner import AgentRunner
from skiller.application.agent.config.event_output_sanitizer import (
    AgentEventOutputSanitizer,
)
from skiller.application.agent.error_mapper import AgentErrorMapper
from skiller.application.agent.feedback import AgentRunnerFeedback
from skiller.application.agent.observer.runtime_event_emitter import AgentRuntimeEventEmitter
from skiller.application.agent.prompt.final_message_extractor import (
    AgentFinalMessageExtractor,
)
from skiller.application.agent.prompt.prompt_builder import AgentPromptBuilder
from skiller.application.agent.tools.agent_tool_execution import AgentToolExecution
from skiller.application.agent.tools.tool_manager import ToolManager
from skiller.application.use_cases.run.append_runtime_event import AppendRuntimeEventUseCase
from skiller.domain.agent.agent_context_store_port import AgentContextStorePort
from skiller.domain.agent.llm_port import LLMPort
from skiller.domain.run.steering_model import SteeringItem, SteeringItemType
from skiller.domain.shared.steering_port import SteeringPort
from skiller.domain.tool.tool_process_model import (
    ToolProcessHandle,
    ToolProcessOutput,
    ToolProcessRequest,
    ToolProcessWait,
    ToolProcessWaitResult,
    ToolProcessWaitStatus,
)


class _NullSteering:
    def append(self, run_id: str, item: SteeringItem) -> None:
        _ = run_id, item

    def pop(self, run_id: str, item_type: SteeringItemType) -> list[SteeringItem]:
        _ = run_id, item_type
        return []


def build_tool_execution(
    *,
    agent_context_store: AgentContextStorePort,
    steering: SteeringPort | None = None,
    tool_manager: ToolManager | None = None,
    append_runtime_event_use_case: AppendRuntimeEventUseCase | None = None,
    event_output_sanitizer: AgentEventOutputSanitizer | None = None,
) -> AgentToolExecution:
    return AgentToolExecution(
        agent_context_store=agent_context_store,
        steering=steering or _NullSteering(),
        tool_manager=tool_manager or ToolManager(tools=[]),
        process_runner=_FakeToolProcessRunner(),
        feedback=AgentRunnerFeedback(),
        event_output_sanitizer=event_output_sanitizer or AgentEventOutputSanitizer(),
        event_emitter=AgentRuntimeEventEmitter(
            append_runtime_event_use_case=append_runtime_event_use_case
        ),
    )


def build_agent_runner(
    *,
    agent_context_store: AgentContextStorePort,
    steering: SteeringPort | None = None,
    llm: LLMPort,
    tool_manager: ToolManager | None = None,
    append_runtime_event_use_case: AppendRuntimeEventUseCase | None = None,
    event_output_sanitizer: AgentEventOutputSanitizer | None = None,
) -> AgentRunner:
    return AgentRunner(
        agent_context_store=agent_context_store,
        llm=llm,
        tool_manager=tool_manager or ToolManager(tools=[]),
        prompt_builder=AgentPromptBuilder(),
        final_message_extractor=AgentFinalMessageExtractor(),
        error_mapper=AgentErrorMapper(),
        feedback=AgentRunnerFeedback(),
        event_output_sanitizer=event_output_sanitizer or AgentEventOutputSanitizer(),
        event_emitter=AgentRuntimeEventEmitter(
            append_runtime_event_use_case=append_runtime_event_use_case
        ),
        tool_execution=build_tool_execution(
            agent_context_store=agent_context_store,
            steering=steering,
            tool_manager=tool_manager or ToolManager(tools=[]),
            append_runtime_event_use_case=append_runtime_event_use_case,
            event_output_sanitizer=event_output_sanitizer,
        ),
    )


class _FakeToolProcessRunner:
    def popen(self, request: ToolProcessRequest) -> ToolProcessHandle:
        return ToolProcessHandle(id="test-process", pid=1)

    def write(self, handle: ToolProcessHandle, payload: str) -> None:
        return None

    def poll(self, handle: ToolProcessHandle) -> int | None:
        return 0

    def read(self, handle: ToolProcessHandle) -> ToolProcessOutput:
        return ToolProcessOutput(exit_code=0, stdout="", stderr="")

    def terminate(self, handle: ToolProcessHandle) -> None:
        return None

    def wait(self, request: ToolProcessWait) -> ToolProcessWaitResult:
        return ToolProcessWaitResult(
            status=ToolProcessWaitStatus.COMPLETED,
            output=self.read(request.handle),
        )
