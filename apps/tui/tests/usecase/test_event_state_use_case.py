from __future__ import annotations

import pytest

from stui.port.event_models import (
    AgentOutputValue,
    ErrorPayload,
    InputReceivedPayload,
    LogEvent,
    LogEventPayload,
    LogEventType,
    OutputPayload,
    RunFinishedPayload,
    RunWaitingPayload,
    StepErrorPayload,
    StepSuccessPayload,
    WaitInputOutputValue,
    WaitWebhookOutputValue,
)
from stui.port.event_port import DEFAULT_POLL_INTERVAL_SECONDS
from stui.port.run_port import CommandAck, CommandAckStatus
from stui.usecase.event_state_use_case import (
    WEBHOOK_POLL_INTERVAL_SECONDS,
    EventStateUseCase,
)
from stui.usecase.event_transcript_mapper import EventTranscriptMapper
from stui.usecase.run_event_context import RunEventContext, RunMode, RunStatus
from stui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    UserInputItem,
    ViewStatusKind,
)

pytestmark = pytest.mark.unit


class FakeAgentPort:
    def __init__(self) -> None:
        self.interrupt_calls: list[str] = []

    def interrupt(self, run_id: str) -> CommandAck:
        self.interrupt_calls.append(run_id)
        return CommandAck(status=CommandAckStatus.ACCEPTED, run_id=run_id)


class FakeEventsPort:
    def __init__(self) -> None:
        self.subscribe_calls: list[tuple[str, object, float]] = []

    def subscribe(
        self,
        *,
        run_id: str,
        listener: object,
        interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    ) -> None:
        self.subscribe_calls.append((run_id, listener, interval_seconds))

    def unsubscribe(self) -> None:
        pass


class FakeObserver:
    def notify(self, events: list[LogEvent]) -> None:
        _ = events

    def get_max_page(self) -> int:
        return 100


def test_event_state_maps_transcript_and_projects_most_recent_event() -> None:
    state = ConsoleScreenState()
    context = _context()
    use_case = _use_case(context=context)

    use_case.execute(
        FakeObserver(),
        state=state,
        events=[
            _event(
                LogEventType.RUN_WAITING,
                step_type="wait_input",
                sequence=2,
                created_at="2026-05-12T10:30:15Z",
                payload=_run_waiting_payload("Write a message."),
            ),
            _event(
                LogEventType.INPUT_RECEIVED,
                sequence=1,
                created_at="2026-05-12T10:30:16Z",
                payload=InputReceivedPayload(payload={"text": "hola"}),
            ),
        ],
    )

    assert len(state.transcript.items) == 2
    assert isinstance(state.transcript.items[-1], UserInputItem)
    assert state.transcript.items[-1].text == "hola"
    assert state.view_status.kind == ViewStatusKind.HIDDEN
    assert context.status == RunStatus.RUNNING


def test_event_state_waiting_input_sets_prompt_and_context() -> None:
    state = ConsoleScreenState()
    context = _context()
    use_case = _use_case(context=context)

    use_case.execute(
        FakeObserver(),
        state=state,
        events=[
            _event(
                LogEventType.RUN_WAITING,
                step_type="wait_input",
                payload=_run_waiting_payload("Write a message."),
            )
        ],
    )

    assert state.view_status.kind == ViewStatusKind.WAITING
    assert state.prompt.waiting_prompt == "Write a message."
    assert context.status == RunStatus.WAITING_INPUT


def test_event_state_waiting_webhook_resubscribes_with_slow_polling() -> None:
    state = ConsoleScreenState()
    context = _context()
    context.run_id = "run-1"
    events_port = FakeEventsPort()
    observer = FakeObserver()
    use_case = _use_case(context=context, events_port=events_port)

    use_case.execute(
        observer,
        state=state,
        events=[
            _event(
                LogEventType.RUN_WAITING,
                step_type="wait_webhook",
                payload=_run_waiting_webhook_payload(),
            )
        ],
    )

    assert state.view_status.kind == ViewStatusKind.WAITING
    assert state.prompt.waiting_prompt == ""
    assert context.status == RunStatus.WAITING_WEBHOOK
    assert events_port.subscribe_calls == [
        ("run-1", observer, WEBHOOK_POLL_INTERVAL_SECONDS)
    ]


def test_event_state_waiting_without_step_type_defaults_to_webhook() -> None:
    state = ConsoleScreenState()
    context = _context()
    use_case = _use_case(context=context)

    use_case.execute(
        FakeObserver(),
        state=state,
        events=[
            _event(
                LogEventType.RUN_WAITING,
                step_type="",
                payload=_run_waiting_payload("Write a message."),
            )
        ],
    )

    assert state.view_status.kind == ViewStatusKind.WAITING
    assert state.prompt.waiting_prompt == ""
    assert context.status == RunStatus.WAITING_WEBHOOK


def test_event_state_step_error_sets_error_and_preserves_prompt_text() -> None:
    state = ConsoleScreenState()
    state.set_prompt(text="draft", cursor_position=5, waiting_prompt="old")
    context = _context()
    use_case = _use_case(context=context)

    use_case.execute(
        FakeObserver(),
        state=state,
        events=[
            _event(
                LogEventType.STEP_ERROR,
                payload=StepErrorPayload(error="boom"),
            )
        ],
    )

    assert state.view_status.kind == ViewStatusKind.ERROR
    assert state.view_status.message == "boom"
    assert state.prompt.text == "draft"
    assert state.prompt.cursor_position == 5
    assert state.prompt.waiting_prompt == ""
    assert context.status == RunStatus.FAILED


def test_event_state_step_success_sets_running_status() -> None:
    state = ConsoleScreenState()
    context = _context()
    use_case = _use_case(context=context)

    use_case.execute(
        FakeObserver(),
        state=state,
        events=[
            _event(
                LogEventType.STEP_SUCCESS,
                sequence=2,
                step_type="agent",
                payload=StepSuccessPayload(
                    output=OutputPayload(
                        text="Done",
                        value=AgentOutputValue(
                            data={
                                "final": "Done",
                                "stop_reason": "final",
                            }
                        ),
                        body_ref=None,
                    ),
                ),
            )
        ],
    )

    assert state.view_status.kind == ViewStatusKind.RUNNING
    assert context.status == RunStatus.RUNNING


def test_event_state_projects_waiting_after_recoverable_agent_failure() -> None:
    state = ConsoleScreenState()
    context = _context()
    use_case = _use_case(context=context)

    use_case.execute(
        FakeObserver(),
        state=state,
        events=[
            _event(
                LogEventType.STEP_SUCCESS,
                sequence=2,
                step_id="verify_minimax",
                step_type="agent",
                payload=StepSuccessPayload(
                    output=OutputPayload(
                        text="LLM request failed",
                        value=AgentOutputValue(
                            data={
                                "message": "Invalid API key.",
                                "stop_reason": "llm_request_failed",
                            }
                        ),
                        body_ref=None,
                    ),
                    next_step_id="route_minimax_validation",
                ),
            ),
            _event(
                LogEventType.RUN_WAITING,
                sequence=3,
                step_id="select_validation_action",
                step_type="wait_input",
                payload=_run_waiting_payload("Choose 1 or 2"),
            ),
        ],
    )

    assert state.view_status.kind == ViewStatusKind.WAITING
    assert state.prompt.waiting_prompt == "Choose 1 or 2"
    assert context.status == RunStatus.WAITING_INPUT


@pytest.mark.parametrize(
    (
        "event_type",
        "payload",
        "expected_view_status",
        "expected_context_status",
        "expected_message",
    ),
    [
        (
            LogEventType.RUN_FINISHED,
            RunFinishedPayload(status="succeeded"),
            ViewStatusKind.HIDDEN,
            RunStatus.SUCCESS,
            "",
        ),
        (
            LogEventType.RUN_FINISHED,
            RunFinishedPayload(status="failed", error="bad run"),
            ViewStatusKind.ERROR,
            RunStatus.FAILED,
            "failed",
        ),
        (
            LogEventType.OBSERVER_LOOP_ERROR,
            ErrorPayload(error="RuntimeError: boom"),
            ViewStatusKind.ERROR,
            RunStatus.RUNNING,
            "Observer error",
        ),
    ],
)
def test_event_state_projects_terminal_and_observer_status(
    event_type: LogEventType,
    payload: LogEventPayload,
    expected_view_status: ViewStatusKind,
    expected_context_status: RunStatus,
    expected_message: str,
) -> None:
    state = ConsoleScreenState()
    context = _context()
    use_case = _use_case(context=context)

    use_case.execute(FakeObserver(), state=state, events=[_event(event_type, payload=payload)])

    assert state.view_status.kind == expected_view_status
    assert state.view_status.message == expected_message
    assert context.status == expected_context_status


def test_event_state_interrupts_running_run_on_observer_error() -> None:
    state = ConsoleScreenState()
    context = _context()
    context.run_id = "run-1"
    agent_port = FakeAgentPort()
    use_case = _use_case(context=context, agent_port=agent_port)

    use_case.execute(
        FakeObserver(),
        state=state,
        events=[
            _event(
                LogEventType.OBSERVER_LOOP_ERROR,
                payload=ErrorPayload(error="RuntimeError: boom"),
            )
        ],
    )

    assert agent_port.interrupt_calls == ["run-1"]


def test_event_state_does_not_interrupt_waiting_run_on_observer_error() -> None:
    state = ConsoleScreenState()
    context = _context()
    context.run_id = "run-1"
    context.status = RunStatus.WAITING_INPUT
    agent_port = FakeAgentPort()
    use_case = _use_case(context=context, agent_port=agent_port)

    use_case.execute(
        FakeObserver(),
        state=state,
        events=[
            _event(
                LogEventType.OBSERVER_LOOP_ERROR,
                payload=ErrorPayload(error="RuntimeError: boom"),
            )
        ],
    )

    assert agent_port.interrupt_calls == []


def _use_case(
    *,
    context: RunEventContext,
    agent_port: FakeAgentPort | None = None,
    events_port: FakeEventsPort | None = None,
) -> EventStateUseCase:
    return EventStateUseCase(
        context=context,
        agent_port=agent_port or FakeAgentPort(),
        events_port=events_port or FakeEventsPort(),
        transcript_mapper=EventTranscriptMapper(),
    )


def _context() -> RunEventContext:
    return RunEventContext(
        run_id="",
        run_name="",
        mode=RunMode.FLOW,
        status=RunStatus.RUNNING,
    )


def _run_waiting_payload(prompt: str) -> RunWaitingPayload:
    return RunWaitingPayload(
        output=OutputPayload(
            text=prompt,
            value=WaitInputOutputValue(prompt=prompt),
            body_ref=None,
        )
    )


def _run_waiting_webhook_payload() -> RunWaitingPayload:
    return RunWaitingPayload(
        output=OutputPayload(
            text="Waiting webhook.",
            value=WaitWebhookOutputValue(webhook="auth", key="token"),
            body_ref=None,
        )
    )


def _event(
    event_type: LogEventType,
    *,
    sequence: int = 1,
    step_id: str | None = None,
    step_type: str | None = None,
    created_at: str = "2026-05-12T10:30:15Z",
    payload: LogEventPayload,
) -> LogEvent:
    return LogEvent(
        sequence=sequence,
        event_id=f"evt-{sequence}",
        run_id="run-1",
        event_type=event_type,
        step_id=step_id,
        step_type=step_type,
        agent_sequence=None,
        created_at=created_at,
        payload=payload,
    )
