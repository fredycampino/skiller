from typing import Any

from skiller.application.use_cases.run.append_runtime_event import (
    AppendRuntimeEventUseCase,
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
            payload={
                "step": step_id,
                "step_type": "agent",
                "turn_id": turn_id,
                "sequence": sequence,
                "message_type": message_type,
                "text": text,
            },
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

        payload: dict[str, Any] = {
            "step": step_id,
            "step_type": "agent",
            "turn_id": turn_id,
            "tool_call_id": tool_call_id,
            "tool": tool,
            "args": args,
        }
        if sequence is not None:
            payload["sequence"] = sequence
        if parent_sequence is not None:
            payload["parent_sequence"] = parent_sequence

        self.append_runtime_event_use_case.execute(
            run_id,
            event_type=RuntimeEventType.AGENT_TOOL_CALL,
            payload=payload,
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
        context_ref: str,
        output: dict[str, Any],
    ) -> None:
        if self.append_runtime_event_use_case is None:
            return

        payload: dict[str, Any] = {
            "step": step_id,
            "step_type": "agent",
            "turn_id": turn_id,
            "tool_call_id": tool_call_id,
            "tool": tool,
            "context_ref": context_ref,
            "output": output,
        }
        if sequence is not None:
            payload["sequence"] = sequence
        if parent_sequence is not None:
            payload["parent_sequence"] = parent_sequence

        self.append_runtime_event_use_case.execute(
            run_id,
            event_type=RuntimeEventType.AGENT_TOOL_RESULT,
            payload=payload,
        )
