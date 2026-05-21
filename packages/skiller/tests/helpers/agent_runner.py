from __future__ import annotations

from skiller.application.agent.agent_runner import AgentRunner
from skiller.application.agent.config.output_truncator import OutputTruncator
from skiller.application.agent.context.agent_context_manager import AgentContextManager
from skiller.application.agent.context.agent_context_publisher import (
    AgentContextPublisher,
)
from skiller.application.agent.event.agent_event_publisher import AgentEventPublisher
from skiller.application.agent.event.agent_event_truncator import (
    AgentEventOutputPolicy,
    AgentEventTruncator,
)
from skiller.application.agent.llmodel.llm_model_manager import LLMModelManager
from skiller.application.agent.mapper.error_mapper import AgentErrorMapper
from skiller.application.agent.mapper.feedback import AgentRunnerFeedback
from skiller.application.agent.prompt.prompt_builder import AgentPromptBuilder
from skiller.application.agent.tools.agent_tool_executor import AgentToolExecutor
from skiller.application.agent.tools.tool_manager import ToolManager
from skiller.application.use_cases.run.append_runtime_event import AppendRuntimeEventUseCase
from skiller.domain.agent.agent_context_model import (
    AgentAssistantMessagePayload,
    AgentContextEntry,
    AgentContextEntryType,
    AgentToolCallPayload,
    AgentToolResultPayload,
)
from skiller.domain.agent.agent_context_store_port import AgentContextStorePort
from skiller.domain.agent.llm_port import LLMPort
from skiller.domain.event.event_model import (
    AgentBodyToolMessage,
    AgentEventPayload,
    AgentLifecyclePayload,
    RuntimeEventType,
)
from skiller.domain.event.runtime_event_store_port import RuntimeEventStorePort
from skiller.domain.run.run_model import RunAgent
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


class _FakeRunStore:
    def __init__(self) -> None:
        self.agents: dict[tuple[str, str], RunAgent] = {}

    def get_agent(self, *, run_id: str, agent_id: str) -> RunAgent | None:
        return self.agents.get((run_id, agent_id))

    def attach_agent(self, *, run_id: str, agent_id: str, context_id: str) -> None:
        self.agents[(run_id, agent_id)] = RunAgent(
            agent_id=agent_id,
            context_id=context_id,
        )


class _UseCaseRuntimeEventStore(RuntimeEventStorePort):
    def __init__(self, append_runtime_event_use_case: AppendRuntimeEventUseCase | None) -> None:
        self.append_runtime_event_use_case = append_runtime_event_use_case

    def emit_max_turns_exhausted(
        self,
        *,
        run_id: str,
        step_id: str,
        turn_id: str,
    ) -> None:
        if self.append_runtime_event_use_case is None:
            return

        self.append_runtime_event_use_case.execute(
            run_id,
            event_type=RuntimeEventType.AGENT_MAX_TURNS_EXHAUSTED,
            step_id=step_id,
            step_type="agent",
            payload=AgentLifecyclePayload(
                turn_id=turn_id,
                stop_reason="max_turns_exhausted",
            ),
        )

    def emit_interrupted(
        self,
        *,
        run_id: str,
        step_id: str,
        turn_id: str,
    ) -> None:
        if self.append_runtime_event_use_case is None:
            return

        self.append_runtime_event_use_case.execute(
            run_id,
            event_type=RuntimeEventType.AGENT_INTERRUPTED,
            step_id=step_id,
            step_type="agent",
            payload=AgentLifecyclePayload(
                turn_id=turn_id,
                stop_reason="interrupted",
            ),
        )

    def emit_assistant_message(
        self,
        *,
        entry: AgentContextEntry,
    ) -> None:
        if self.append_runtime_event_use_case is None:
            return
        if entry.entry_type != AgentContextEntryType.ASSISTANT_MESSAGE:
            raise ValueError("Assistant event requires assistant_message entry")
        if not isinstance(entry.payload, AgentAssistantMessagePayload):
            raise ValueError("Assistant event requires AgentAssistantMessagePayload")

        self.append_runtime_event_use_case.execute(
            entry.run_id,
            event_type=RuntimeEventType.AGENT_ASSISTANT_MESSAGE,
            payload=AgentEventPayload(
                step_id=entry.source_step_id,
                turn_id=entry.payload.turn_id,
                agent_sequence=entry.sequence,
                body=AgentBodyToolMessage(
                    total_tokens=entry.payload.total_tokens or 0,
                    text=entry.payload.text,
                ),
            ),
        )

    def emit_final_assistant_message(
        self,
        *,
        entry: AgentContextEntry,
    ) -> None:
        if self.append_runtime_event_use_case is None:
            return
        if entry.entry_type != AgentContextEntryType.ASSISTANT_MESSAGE:
            raise ValueError("Final assistant event requires assistant_message entry")
        if not isinstance(entry.payload, AgentAssistantMessagePayload):
            raise ValueError("Final assistant event requires AgentAssistantMessagePayload")

        self.append_runtime_event_use_case.execute(
            entry.run_id,
            event_type=RuntimeEventType.AGENT_FINAL_ASSISTANT_MESSAGE,
            payload=AgentEventPayload(
                step_id=entry.source_step_id,
                turn_id=entry.payload.turn_id,
                agent_sequence=entry.sequence,
                body=AgentBodyToolMessage(
                    total_tokens=entry.payload.total_tokens or 0,
                    text=entry.payload.text,
                ),
            ),
        )

    def emit_tool_call(
        self,
        *,
        entry: AgentContextEntry,
    ) -> None:
        if self.append_runtime_event_use_case is None:
            return
        if entry.entry_type != AgentContextEntryType.TOOL_CALL:
            raise ValueError("Tool call event requires tool_call entry")
        if not isinstance(entry.payload, AgentToolCallPayload):
            raise ValueError("Tool call event requires AgentToolCallPayload")

        self.append_runtime_event_use_case.execute(
            entry.run_id,
            event_type=RuntimeEventType.AGENT_TOOL_CALL,
            payload=AgentEventPayload(
                step_id=entry.source_step_id,
                turn_id=entry.payload.turn_id,
                agent_sequence=entry.sequence,
                body=entry.payload,
            ),
        )

    def emit_tool_result(
        self,
        *,
        entry: AgentContextEntry,
    ) -> None:
        if self.append_runtime_event_use_case is None:
            return
        if entry.entry_type != AgentContextEntryType.TOOL_RESULT:
            raise ValueError("Tool result event requires tool_result entry")
        if not isinstance(entry.payload, AgentToolResultPayload):
            raise ValueError("Tool result event requires AgentToolResultPayload")

        self.append_runtime_event_use_case.execute(
            entry.run_id,
            event_type=RuntimeEventType.AGENT_TOOL_RESULT,
            payload=AgentEventPayload(
                step_id=entry.source_step_id,
                turn_id=entry.payload.turn_id,
                agent_sequence=entry.sequence,
                body=entry.payload,
            ),
        )

    def append_event(self, event):  # noqa: ANN001
        if self.append_runtime_event_use_case is None:
            return "event-1"

        result = self.append_runtime_event_use_case.execute(
            event.run_id,
            event_type=event.type,
            payload=event.payload,
            step_id=event.step_id,
            step_type=event.step_type,
            agent_sequence=event.agent_sequence,
        )
        if result is None:
            return "event-1"
        return result.event_id

    def list_events(self, run_id: str, *, after_sequence=None, limit=None):  # noqa: ANN001
        raise NotImplementedError

    def get_last_event(self, run_id: str):  # noqa: ANN201
        raise NotImplementedError


def build_tool_execution(
    *,
    agent_context_store: AgentContextStorePort,
    steering: SteeringPort | None = None,
    tool_manager: ToolManager | None = None,
    append_runtime_event_use_case: AppendRuntimeEventUseCase | None = None,
) -> AgentToolExecutor:
    context_publisher = AgentContextPublisher(
        agent_context_store,
        _FakeRunStore(),
        AgentRunnerFeedback(),
    )
    runtime_event_store = _UseCaseRuntimeEventStore(append_runtime_event_use_case)
    return AgentToolExecutor(
        context_publisher=context_publisher,
        event_publisher=AgentEventPublisher(
            runtime_event_store,
            AgentEventTruncator(
                AgentEventOutputPolicy(),
                OutputTruncator(),
            ),
        ),
        steering=steering or _NullSteering(),
        tool_manager=tool_manager or ToolManager(tools=[]),
        process_runner=_FakeToolProcessRunner(),
        feedback=AgentRunnerFeedback(),
    )


def build_agent_runner(
    *,
    agent_context_store: AgentContextStorePort,
    steering: SteeringPort | None = None,
    llm: LLMPort,
    tool_manager: ToolManager | None = None,
    append_runtime_event_use_case: AppendRuntimeEventUseCase | None = None,
) -> AgentRunner:
    runtime_event_store = _UseCaseRuntimeEventStore(append_runtime_event_use_case)
    run_store = _FakeRunStore()
    llm_model = LLMModelManager(
        create_null_client=lambda provider: llm,
        create_fake_client=lambda provider: llm,
        create_openai_client=lambda provider: llm,
    )
    return AgentRunner(
        agent_context_store=agent_context_store,
        llm_model=llm_model,
        context_manager=AgentContextManager(
            agent_context_store=agent_context_store,
            prompt_builder=AgentPromptBuilder(),
        ),
        error_mapper=AgentErrorMapper(),
        feedback=AgentRunnerFeedback(),
        context_publisher=AgentContextPublisher(
            agent_context_store,
            run_store,
            AgentRunnerFeedback(),
        ),
        event_publisher=AgentEventPublisher(
            runtime_event_store,
            AgentEventTruncator(
                AgentEventOutputPolicy(),
                OutputTruncator(),
            ),
        ),
        tool_execution=build_tool_execution(
            agent_context_store=agent_context_store,
            steering=steering,
            tool_manager=tool_manager or ToolManager(tools=[]),
            append_runtime_event_use_case=append_runtime_event_use_case,
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
