from __future__ import annotations

import pytest

from stui.port.event_models import (
    ActionDonePayload,
    ActionOpenUrlValue,
    AgentAssistantMessagePayload,
    AgentFinalAssistantMessagePayload,
    AgentLifecyclePayload,
    AgentOutputValue,
    AgentStopReason,
    AgentToolCallPayload,
    AgentToolResultPayload,
    AgentToolResultStatus,
    AssignOutputValue,
    ErrorPayload,
    InputReceivedPayload,
    LogEvent,
    LogEventPayload,
    LogEventType,
    NotifyActionStatus,
    NotifyActionType,
    NotifyActionValue,
    NotifyOutputFormat,
    NotifyOutputValue,
    OutputPayload,
    RouteOutputValue,
    RunFinishedPayload,
    RunResumePayload,
    RunWaitingPayload,
    ShellOutputValue,
    StepErrorPayload,
    StepStartedPayload,
    StepSuccessPayload,
    WaitInputOutputValue,
    WaitWebhookOutputValue,
)
from stui.usecase.event_transcript_mapper import EventTranscriptMapper
from stui.viewmodel.console_screen_state import (
    AgentAssistantMessageItem,
    AgentFinalAssistantMessageItem,
    AgentStepFinalOutputItem,
    AgentSystemNoticeItem,
    AgentToolCallItem,
    AgentToolResultItem,
    DispatchErrorItem,
    NotifyActionDoneItem,
    OutputFormat,
    RunFinishedItem,
    RunWaitingInputItem,
    RunWaitingWebhookItem,
    StepErrorItem,
    StepNotifyActionItem,
    StepNotifyOutputItem,
    StepOutputItem,
    StepShellOutputItem,
    UserInputItem,
)

pytestmark = pytest.mark.unit


def test_event_transcript_mapper_renders_agent_tool_turn() -> None:
    mapper = EventTranscriptMapper()

    items = mapper.to_transcript(
        [
            _event(
                LogEventType.AGENT_ASSISTANT_MESSAGE,
                step_id="support_agent",
                step_type="agent",
                payload=AgentAssistantMessagePayload(
                    text="I will inspect the repository state.",
                    total_tokens=1000,
                ),
            ),
            _event(
                LogEventType.AGENT_TOOL_CALL,
                sequence=2,
                step_id="support_agent",
                step_type="agent",
                payload=AgentToolCallPayload(
                    type="tool_call",
                    turn_id="turn-1",
                    parent_sequence=1,
                    tool_call_id="call-1",
                    tool="shell",
                    args={"command": "git status --short"},
                ),
            ),
            _event(
                LogEventType.AGENT_TOOL_RESULT,
                sequence=3,
                step_id="support_agent",
                step_type="agent",
                payload=AgentToolResultPayload(
                    type="tool_result",
                    turn_id="turn-1",
                    parent_sequence=1,
                    tool_call_id="call-1",
                    tool="shell",
                    status=AgentToolResultStatus.COMPLETED,
                    data={"ok": True, "exit_code": 0},
                    text="Command completed successfully.",
                    error=None,
                ),
            ),
        ],
    )

    assert isinstance(items[0], AgentAssistantMessageItem)
    assert isinstance(items[1], AgentToolCallItem)
    assert isinstance(items[2], AgentToolResultItem)
    assert items[1].command == "git status --short"
    assert items[2].preview == "Command completed successfully."


def test_event_transcript_mapper_shows_interrupted_tool_result_error() -> None:
    mapper = EventTranscriptMapper()

    items = mapper.to_transcript(
        [
            _event(
                LogEventType.AGENT_TOOL_RESULT,
                step_id="support_agent",
                step_type="agent",
                payload=AgentToolResultPayload(
                    type="tool_result",
                    turn_id="turn-1",
                    parent_sequence=1,
                    tool_call_id="call-1",
                    tool="shell",
                    status=AgentToolResultStatus.INTERRUPTED,
                    data={"error": "interrupted"},
                    text=None,
                    error="Tool execution interrupted by user",
                ),
            ),
        ],
    )

    assert len(items) == 1
    assert isinstance(items[0], AgentToolResultItem)
    assert items[0].preview == "Tool execution interrupted by user"


def test_event_transcript_mapper_uses_action_done_as_notify_action_done_item() -> None:
    mapper = EventTranscriptMapper()

    items = mapper.to_transcript(
        [
            _event(
                LogEventType.ACTION_DONE,
                sequence=2,
                step_id="auth_link",
                step_type="notify",
                payload=ActionDonePayload(
                    action_type=NotifyActionType.OPEN_URL,
                    status=NotifyActionStatus.DONE,
                ),
            ),
        ],
    )

    assert len(items) == 1
    assert isinstance(items[0], NotifyActionDoneItem)
    assert items[0].run_id == "run-1"
    assert items[0].step_id == "auth_link"
    assert items[0].step_type == "notify"
    assert items[0].action_type == "open_url"
    assert items[0].status == "done"


def test_event_transcript_mapper_uses_final_assistant_message_as_agent_final_output() -> None:
    mapper = EventTranscriptMapper()

    items = mapper.to_transcript(
        [
            _event(
                LogEventType.AGENT_FINAL_ASSISTANT_MESSAGE,
                sequence=2,
                step_id="support_agent",
                step_type="agent",
                payload=AgentFinalAssistantMessagePayload(
                    text="Hecho completo.",
                    total_tokens=2144,
                ),
            ),
        ],
    )

    assert len(items) == 1
    assert isinstance(items[0], AgentFinalAssistantMessageItem)
    assert items[0].text == "Hecho completo."
    assert items[0].total_tokens == 2144


def test_event_transcript_mapper_uses_agent_step_success_as_final_output() -> None:
    mapper = EventTranscriptMapper()

    items = mapper.to_transcript(
        [
            _event(
                LogEventType.STEP_SUCCESS,
                sequence=2,
                step_id="support_agent",
                step_type="agent",
                payload=StepSuccessPayload(
                    output=OutputPayload(
                        text="Hecho completo.",
                        value=AgentOutputValue(
                            data={
                                "final": {"text": "Hecho completo."},
                                "usage": {
                                    "prompt_tokens": 100,
                                    "completion_tokens": 25,
                                    "total_tokens": 125,
                                    "provider": "openai",
                                    "model": "fake",
                                },
                            }
                        ),
                        body_ref=None,
                    )
                ),
            ),
        ],
    )

    assert len(items) == 1
    assert isinstance(items[0], AgentStepFinalOutputItem)
    assert items[0].text == "Hecho completo."
    assert items[0].usage is not None
    assert items[0].usage.prompt_tokens == 100
    assert items[0].usage.completion_tokens == 25
    assert items[0].usage.total_tokens == 125
    assert items[0].usage.provider == "openai"
    assert items[0].usage.model == "fake"


def test_event_transcript_mapper_uses_notify_step_success_as_step_notify_output() -> None:
    mapper = EventTranscriptMapper()

    items = mapper.to_transcript(
        [
            _event(
                LogEventType.STEP_SUCCESS,
                sequence=2,
                step_id="intro",
                step_type="notify",
                payload=StepSuccessPayload(
                    output=OutputPayload(
                        text="Skiller.run",
                        value=NotifyOutputValue(message="Skiller.run"),
                        body_ref=None,
                    )
                ),
            ),
        ],
    )

    assert len(items) == 1
    assert isinstance(items[0], StepNotifyOutputItem)
    assert items[0].step_type == "notify"
    assert items[0].message == "Skiller.run"
    assert items[0].format == OutputFormat.SIMPLE
    assert items[0].icon == "•"
    assert items[0].muted is False


def test_event_transcript_mapper_uses_notify_output_format() -> None:
    mapper = EventTranscriptMapper()

    items = mapper.to_transcript(
        [
            _event(
                LogEventType.STEP_SUCCESS,
                sequence=2,
                step_id="intro",
                step_type="notify",
                payload=StepSuccessPayload(
                    output=OutputPayload(
                        text="**Skiller.run**",
                        value=NotifyOutputValue(
                            message="**Skiller.run**",
                            format=NotifyOutputFormat.MARKDOWN,
                        ),
                        body_ref=None,
                    )
                ),
            ),
        ],
    )

    assert len(items) == 1
    assert isinstance(items[0], StepNotifyOutputItem)
    assert items[0].format == OutputFormat.MARKDOWN


def test_event_transcript_mapper_uses_notify_action_as_step_notify_action() -> None:
    mapper = EventTranscriptMapper()

    items = mapper.to_transcript(
        [
            _event(
                LogEventType.STEP_SUCCESS,
                sequence=2,
                step_id="auth_link",
                step_type="notify",
                payload=StepSuccessPayload(
                    output=OutputPayload(
                        text="Authorize the app",
                        value=NotifyActionValue(
                            message="Authorize the app",
                            action_type=NotifyActionType.OPEN_URL,
                            action=ActionOpenUrlValue(
                                label="Open authorization",
                                url="https://example.com/oauth/start",
                                status=NotifyActionStatus.PENDING,
                                auto_open=True,
                            ),
                        ),
                        body_ref=None,
                    )
                ),
            ),
        ],
    )

    assert len(items) == 1
    assert isinstance(items[0], StepNotifyActionItem)
    assert items[0].step_id == "auth_link"
    assert items[0].step_type == "notify"
    assert items[0].message == "Authorize the app"
    assert items[0].action_type == "open_url"
    assert items[0].label == "Open authorization"
    assert items[0].url == "https://example.com/oauth/start"
    assert items[0].status == "pending"
    assert items[0].auto_open is True
    assert items[0].icon == "•"
    assert items[0].muted is False


def test_event_transcript_mapper_uses_generic_step_success_as_step_output() -> None:
    mapper = EventTranscriptMapper()

    items = mapper.to_transcript(
        [
            _event(
                LogEventType.STEP_SUCCESS,
                sequence=2,
                step_id="assign_sample",
                step_type="assign",
                payload=StepSuccessPayload(
                    output=OutputPayload(
                        text="Values assigned.",
                        value=AssignOutputValue(assigned={"action": "retry"}),
                        body_ref=None,
                    )
                ),
            ),
        ],
    )

    assert len(items) == 1
    assert isinstance(items[0], StepOutputItem)
    assert items[0].step_type == "assign"
    assert items[0].format == OutputFormat.SIMPLE
    assert items[0].icon == "⇢"


def test_event_transcript_mapper_uses_shell_step_success_as_step_shell_output() -> None:
    mapper = EventTranscriptMapper()

    items = mapper.to_transcript(
        [
            _event(
                LogEventType.STEP_SUCCESS,
                sequence=2,
                step_id="intro_pause",
                step_type="shell",
                payload=StepSuccessPayload(
                    output=OutputPayload(
                        text="Shell command completed.",
                        value=ShellOutputValue(
                            ok=True,
                            exit_code=0,
                            stdout="ready",
                            stderr="",
                        ),
                        body_ref=None,
                    )
                ),
            ),
        ],
    )

    assert len(items) == 1
    assert isinstance(items[0], StepShellOutputItem)
    assert items[0].step_type == "shell"
    assert items[0].output == "ready"
    assert items[0].format == OutputFormat.SIMPLE
    assert items[0].icon == "▫"


def test_event_transcript_mapper_renders_route_step_output_with_arrow_icon() -> None:
    mapper = EventTranscriptMapper()

    items = mapper.to_transcript(
        [
            _event(
                LogEventType.STEP_SUCCESS,
                sequence=2,
                step_id="switch_sample",
                step_type="switch",
                payload=StepSuccessPayload(
                    output=OutputPayload(
                        text="Route selected: when_sample.",
                        value=RouteOutputValue(next_step_id="when_sample"),
                        body_ref=None,
                    )
                ),
            ),
        ],
    )

    assert len(items) == 1
    assert isinstance(items[0], StepOutputItem)
    assert items[0].output == "when_sample."
    assert items[0].icon == "↳"


def test_event_transcript_mapper_renders_input_received() -> None:
    mapper = EventTranscriptMapper()

    items = mapper.to_transcript(
        [
            _event(
                LogEventType.INPUT_RECEIVED,
                payload=InputReceivedPayload(payload={"text": "hola mundo"}),
            )
        ],
    )

    assert len(items) == 1
    assert isinstance(items[0], UserInputItem)
    assert items[0].text == "hola mundo"


def test_event_transcript_mapper_ignores_run_resume() -> None:
    mapper = EventTranscriptMapper()

    items = mapper.to_transcript(
        [
            _event(
                LogEventType.RUN_RESUME,
                payload=RunResumePayload(source="manual"),
            )
        ],
    )

    assert items == []


def test_event_transcript_mapper_ignores_wait_input_step_success() -> None:
    mapper = EventTranscriptMapper()

    items = mapper.to_transcript(
        [
            _event(
                LogEventType.STEP_SUCCESS,
                step_id="ask_user",
                step_type="wait_input",
                payload=StepSuccessPayload(
                    output=OutputPayload(
                        text="Input received.",
                        value=WaitInputOutputValue(payload={"text": "hola mundo"}),
                        body_ref=None,
                    )
                ),
            )
        ],
    )

    assert items == []


def test_event_transcript_mapper_orders_events_by_created_at_and_sequence() -> None:
    mapper = EventTranscriptMapper()

    items = mapper.to_transcript(
        [
            _event(
                LogEventType.INPUT_RECEIVED,
                sequence=3,
                payload=InputReceivedPayload(payload={"text": "third"}),
                created_at="2026-05-12T10:30:16Z",
            ),
            _event(
                LogEventType.INPUT_RECEIVED,
                sequence=2,
                payload=InputReceivedPayload(payload={"text": "second"}),
                created_at="2026-05-12T10:30:15Z",
            ),
            _event(
                LogEventType.INPUT_RECEIVED,
                sequence=1,
                payload=InputReceivedPayload(payload={"text": "first"}),
                created_at="2026-05-12T10:30:15Z",
            ),
        ],
    )

    assert [item.text for item in items if isinstance(item, UserInputItem)] == [
        "first",
        "second",
        "third",
    ]


def test_event_transcript_mapper_renders_agent_interrupted_notice_and_final_output() -> None:
    mapper = EventTranscriptMapper()

    items = mapper.to_transcript(
        [
            _event(
                LogEventType.AGENT_INTERRUPTED,
                step_id="support_agent",
                step_type="agent",
                payload=AgentLifecyclePayload(
                    turn_id="turn-7",
                    stop_reason=AgentStopReason.INTERRUPTED,
                ),
            ),
            _event(
                LogEventType.STEP_SUCCESS,
                sequence=2,
                step_id="support_agent",
                step_type="agent",
                payload=StepSuccessPayload(
                    output=OutputPayload(
                        text="",
                        value=AgentOutputValue(data={"stop_reason": "interrupted"}),
                        body_ref=None,
                    )
                ),
            ),
        ],
    )

    assert len(items) == 2
    assert isinstance(items[0], AgentSystemNoticeItem)
    assert items[0].text == "Interrupted by user"
    assert isinstance(items[1], AgentStepFinalOutputItem)
    assert items[1].text == "Interrupted by user"


def test_event_transcript_mapper_renders_waiting_output() -> None:
    mapper = EventTranscriptMapper()

    items = mapper.to_transcript(
        [
            _event(
                LogEventType.STEP_STARTED,
                step_id="ask_user",
                step_type="wait_input",
                payload=StepStartedPayload(),
            ),
            _event(
                LogEventType.RUN_WAITING,
                sequence=2,
                step_id="ask_user",
                step_type="wait_input",
                payload=RunWaitingPayload(
                    output=OutputPayload(
                        text="Write a message.",
                        value=WaitInputOutputValue(prompt="Write a message."),
                        body_ref=None,
                    )
                ),
            ),
        ],
    )

    assert len(items) == 1
    assert isinstance(items[0], RunWaitingInputItem)
    assert items[0].step_type == "wait_input"
    assert items[0].step_id == "ask_user"
    assert items[0].prompt == "Write a message."


def test_event_transcript_mapper_renders_waiting_webhook_output() -> None:
    mapper = EventTranscriptMapper()

    items = mapper.to_transcript(
        [
            _event(
                LogEventType.STEP_STARTED,
                step_id="wait_authorization",
                step_type="wait_webhook",
                payload=StepStartedPayload(),
            ),
            _event(
                LogEventType.RUN_WAITING,
                sequence=2,
                step_id="wait_authorization",
                step_type="wait_webhook",
                payload=RunWaitingPayload(
                    output=OutputPayload(
                        text="",
                        value=WaitWebhookOutputValue(
                            webhook="example-auth",
                            key="GrbyVerTlIkPm33R-DbTe_7h3WKNbKkl",
                        ),
                        body_ref=None,
                    )
                ),
            ),
        ],
    )

    assert len(items) == 1
    assert isinstance(items[0], RunWaitingWebhookItem)
    assert items[0].step_type == "wait_webhook"
    assert items[0].step_id == "wait_authorization"
    assert items[0].webhook == "example-auth"
    assert items[0].key == "GrbyVerTlIkPm33R-DbTe_7h3WKNbKkl"
    assert items[0].icon == "↯"


def test_event_transcript_mapper_surfaces_observer_loop_error() -> None:
    mapper = EventTranscriptMapper()

    items = mapper.to_transcript(
        [
            _event(
                LogEventType.OBSERVER_LOOP_ERROR,
                payload=ErrorPayload(error="RuntimeError: boom"),
            )
        ],
    )

    assert len(items) == 1
    assert isinstance(items[0], DispatchErrorItem)
    assert items[0].message == "RuntimeError: boom"


def test_event_transcript_mapper_uses_step_error_item_for_step_error() -> None:
    mapper = EventTranscriptMapper()

    items = mapper.to_transcript(
        [
            _event(
                LogEventType.STEP_ERROR,
                step_id="register_auth_webhook",
                step_type="shell",
                payload=StepErrorPayload(error="shell command path escapes allowed_paths"),
            )
        ],
    )

    assert len(items) == 1
    assert isinstance(items[0], StepErrorItem)
    assert items[0].step_id == "register_auth_webhook"
    assert items[0].step_type == "shell"
    assert items[0].message == "shell command path escapes allowed_paths"


def test_event_transcript_mapper_uses_muted_run_status_for_failed_run_finished(
) -> None:
    mapper = EventTranscriptMapper()

    items = mapper.to_transcript(
        [
            _event(
                LogEventType.RUN_FINISHED,
                payload=RunFinishedPayload(
                    status="FAILED",
                    error="shell command path escapes allowed_paths",
                ),
            )
        ],
    )

    assert len(items) == 1
    assert isinstance(items[0], RunFinishedItem)
    assert items[0].status == "error"
    assert items[0].message == "failed"


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
