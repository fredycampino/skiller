from typing import Any

from skiller.application.use_cases.run.append_runtime_event import AppendRuntimeEventUseCase
from skiller.domain.agent.agent_context_model import (
    AgentAssistantMessagePayload,
    AgentToolCallPayload,
    AgentToolResultPayload,
)
from skiller.domain.event.event_model import (
    AgentEventPayload,
    AgentLifecyclePayload,
    RuntimeEventType,
)


class AgentRuntimeEventEmitter:
    def __init__(self, append_runtime_event_use_case: AppendRuntimeEventUseCase | None) -> None:
        self.append_runtime_event_use_case = append_runtime_event_use_case

    def emit_assistant_message(
        self,
        *,
        run_id: str,
        step_id: str,
        turn_id: str,
        sequence: int,
        message_type: str,
        text: str,
    ) -> None:
        if self.append_runtime_event_use_case is None:
            return

        self.append_runtime_event_use_case.execute(
            run_id,
            event_type=RuntimeEventType.AGENT_ASSISTANT_MESSAGE,
            payload=AgentEventPayload(
                step_id=step_id,
                turn_id=turn_id,
                agent_sequence=sequence,
                body=AgentAssistantMessagePayload(
                    turn_id=turn_id,
                    message_type=message_type,
                    text=text,
                ),
            ),
        )

    def emit_tool_call(
        self,
        *,
        run_id: str,
        step_id: str,
        turn_id: str,
        sequence: int | None = None,
        parent_sequence: int | None = None,
        tool_call_id: str,
        tool: str,
        args: dict[str, Any],
    ) -> None:
        if self.append_runtime_event_use_case is None:
            return

        self.append_runtime_event_use_case.execute(
            run_id,
            event_type=RuntimeEventType.AGENT_TOOL_CALL,
            payload=AgentEventPayload(
                step_id=step_id,
                turn_id=turn_id,
                agent_sequence=sequence or 0,
                body=AgentToolCallPayload(
                    turn_id=turn_id,
                    parent_sequence=parent_sequence,
                    tool_call_id=tool_call_id,
                    tool=tool,
                    args=args,
                ),
            ),
        )

    def emit_tool_result(
        self,
        *,
        run_id: str,
        step_id: str,
        turn_id: str,
        sequence: int | None = None,
        parent_sequence: int | None = None,
        tool_call_id: str,
        tool: str,
        status: str,
        data: dict[str, Any],
        text: str | None,
        error: str | None,
    ) -> None:
        if self.append_runtime_event_use_case is None:
            return

        self.append_runtime_event_use_case.execute(
            run_id,
            event_type=RuntimeEventType.AGENT_TOOL_RESULT,
            payload=AgentEventPayload(
                step_id=step_id,
                turn_id=turn_id,
                agent_sequence=sequence or 0,
                body=AgentToolResultPayload(
                    turn_id=turn_id,
                    parent_sequence=parent_sequence,
                    tool_call_id=tool_call_id,
                    tool=tool,
                    status=status,
                    data=data,
                    text=text,
                    error=error,
                ),
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
