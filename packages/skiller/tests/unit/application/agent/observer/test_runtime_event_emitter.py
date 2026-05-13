import pytest

from skiller.application.agent.observer.runtime_event_emitter import AgentRuntimeEventEmitter
from skiller.domain.event.event_model import (
    RuntimeEventPayload,
    RuntimeEventType,
    runtime_event_payload_to_dict,
)

pytestmark = pytest.mark.unit


class _FakeAppendRuntimeEventUseCase:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def execute(
        self,
        run_id: str,
        *,
        event_type: RuntimeEventType,
        payload: RuntimeEventPayload | dict[str, object] | None = None,
        step_id: str | None = None,
        step_type=None,  # noqa: ANN001
        execution=None,  # noqa: ANN001
        next_step_id: str | None = None,
        error: str | None = None,
    ) -> None:
        self.calls.append(
            {
                "run_id": run_id,
                "event_type": event_type,
                "payload": (
                    runtime_event_payload_to_dict(payload)
                    if payload is not None
                    else None
                ),
                "step_id": step_id,
                "step_type": step_type,
                "execution": execution,
                "next_step_id": next_step_id,
                "error": error,
            }
        )


def test_agent_runtime_event_emitter_emits_tool_call_and_result() -> None:
    append_event = _FakeAppendRuntimeEventUseCase()
    emitter = AgentRuntimeEventEmitter(append_runtime_event_use_case=append_event)

    emitter.emit_assistant_message(
        run_id="run-1",
        step_id="support_agent",
        turn_id="turn-1",
        sequence=2,
        message_type="tool_calls",
        text="I will inspect the repo first.",
    )
    emitter.emit_tool_call(
        run_id="run-1",
        step_id="support_agent",
        turn_id="turn-1",
        sequence=3,
        parent_sequence=2,
        tool_call_id="call-1",
        tool="shell",
        args={"command": "git status --short"},
    )
    emitter.emit_tool_result(
        run_id="run-1",
        step_id="support_agent",
        turn_id="turn-1",
        sequence=4,
        parent_sequence=2,
        tool_call_id="call-1",
        tool="shell",
        status="completed",
        data={"stdout": "M src/app.py"},
        text="M src/app.py",
        error=None,
    )

    assert append_event.calls == [
        {
            "run_id": "run-1",
            "event_type": RuntimeEventType.AGENT_ASSISTANT_MESSAGE,
            "payload": {
                "step_id": "support_agent",
                "turn_id": "turn-1",
                "agent_sequence": 2,
                "body": {
                    "type": "assistant_message",
                    "turn_id": "turn-1",
                    "message_type": "tool_calls",
                    "text": "I will inspect the repo first.",
                },
            },
            "step_id": None,
            "step_type": None,
            "execution": None,
            "next_step_id": None,
            "error": None,
        },
        {
            "run_id": "run-1",
            "event_type": RuntimeEventType.AGENT_TOOL_CALL,
            "payload": {
                "step_id": "support_agent",
                "turn_id": "turn-1",
                "agent_sequence": 3,
                "body": {
                    "type": "tool_call",
                    "turn_id": "turn-1",
                    "parent_sequence": 2,
                    "tool_call_id": "call-1",
                    "tool": "shell",
                    "args": {"command": "git status --short"},
                },
            },
            "step_id": None,
            "step_type": None,
            "execution": None,
            "next_step_id": None,
            "error": None,
        },
        {
            "run_id": "run-1",
            "event_type": RuntimeEventType.AGENT_TOOL_RESULT,
            "payload": {
                "step_id": "support_agent",
                "turn_id": "turn-1",
                "agent_sequence": 4,
                "body": {
                    "type": "tool_result",
                    "turn_id": "turn-1",
                    "parent_sequence": 2,
                    "tool_call_id": "call-1",
                    "tool": "shell",
                    "status": "completed",
                    "data": {"stdout": "M src/app.py"},
                    "text": "M src/app.py",
                    "error": None,
                },
            },
            "step_id": None,
            "step_type": None,
            "execution": None,
            "next_step_id": None,
            "error": None,
        },
    ]


def test_agent_runtime_event_emitter_emits_agent_finish_events() -> None:
    append_event = _FakeAppendRuntimeEventUseCase()
    emitter = AgentRuntimeEventEmitter(append_runtime_event_use_case=append_event)

    emitter.emit_interrupted(
        run_id="run-1",
        step_id="support_agent",
        turn_id="turn-3",
    )
    emitter.emit_max_turns_exhausted(
        run_id="run-1",
        step_id="support_agent",
        turn_id="turn-4",
    )

    assert append_event.calls == [
        {
            "run_id": "run-1",
            "event_type": RuntimeEventType.AGENT_INTERRUPTED,
            "payload": {
                "turn_id": "turn-3",
                "stop_reason": "interrupted",
            },
            "step_id": "support_agent",
            "step_type": "agent",
            "execution": None,
            "next_step_id": None,
            "error": None,
        },
        {
            "run_id": "run-1",
            "event_type": RuntimeEventType.AGENT_MAX_TURNS_EXHAUSTED,
            "payload": {
                "turn_id": "turn-4",
                "stop_reason": "max_turns_exhausted",
            },
            "step_id": "support_agent",
            "step_type": "agent",
            "execution": None,
            "next_step_id": None,
            "error": None,
        },
    ]


def test_agent_runtime_event_emitter_skips_when_not_configured() -> None:
    emitter = AgentRuntimeEventEmitter(append_runtime_event_use_case=None)

    emitter.emit_assistant_message(
        run_id="run-1",
        step_id="support_agent",
        turn_id="turn-1",
        sequence=2,
        message_type="final",
        text="Done.",
    )
    emitter.emit_tool_call(
        run_id="run-1",
        step_id="support_agent",
        turn_id="turn-1",
        sequence=3,
        parent_sequence=2,
        tool_call_id="call-1",
        tool="shell",
        args={},
    )
    emitter.emit_tool_result(
        run_id="run-1",
        step_id="support_agent",
        turn_id="turn-1",
        sequence=4,
        parent_sequence=2,
        tool_call_id="call-1",
        tool="shell",
        status="completed",
        data={},
        text="",
        error=None,
    )
