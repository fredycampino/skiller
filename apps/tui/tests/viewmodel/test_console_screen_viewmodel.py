from __future__ import annotations

import asyncio
import json

import pytest

import stui.usecase.list_runs_use_case as list_runs_use_case_module
import stui.usecase.run_command_use_case as run_command_use_case_module
from apps.tui.tests.support import (
    FakeAgentPort,
    FakeEventsPort,
    FakeRunsPort,
    build_viewmodel,
    make_runs_port_item,
    patched_to_thread,
)
from stui.port.event_models import (
    AgentAssistantMessagePayload,
    AgentAssistantMessageType,
    AgentToolCallPayload,
    AgentToolResultPayload,
    AgentToolResultStatus,
    InputReceivedPayload,
    LogEvent,
    LogEventPayload,
    LogEventType,
    OutputPayload,
    RunFinishedPayload,
    RunResumePayload,
    RunWaitingPayload,
    StepStartedPayload,
    StepSuccessPayload,
)
from stui.port.run_port import (
    CommandAck,
    CommandAckStatus,
    RunDispatch,
    RunDispatchError,
    RunDispatchErrorKind,
    RunRuntimeStatus,
    RunRuntimeStatusKind,
)
from stui.port.runs_port import RunsPortItem
from stui.port.waiting_port import WaitingInputAck, WaitingInputStatus
from stui.usecase import (
    interrupt_agent_turn_use_case as interrupt_agent_turn_use_case_module,
)
from stui.usecase import (
    submit_waiting_input_use_case as submit_waiting_input_use_case_module,
)
from stui.usecase.run_event_context import RunMode, RunStatus
from stui.viewmodel.console_screen_state import (
    AgentAssistantMessageItem,
    AgentToolCallItem,
    AgentToolResultItem,
    CompletionItem,
    CompletionState,
    ConsoleScreenState,
    DispatchErrorItem,
    InfoItem,
    OutputFormat,
    PromptMode,
    RunAckItem,
    RunOutputItem,
    RunResumeItem,
    RunStatusItem,
    RunStepItem,
    RunWaitingInputItem,
    UserInputItem,
    ViewStatusKind,
)
from stui.viewmodel.console_screen_viewmodel import ConsoleScreenViewModel

pytestmark = pytest.mark.unit

_INPUT_RECEIVED_OUTPUT = (
    '{"body_ref":null,"text":"Input received.",'
    '"value":{"payload":{"text":"hola"}}}'
)

_INPUT_RECEIVED_OUTPUT_TRUNCATED = (
    '{"body_ref":null,"text":"Input received.",'
    '"value":{"payload":{"text":"hola mundo loca"}}}...'
)

_WAITING_PROMPT_OUTPUT = (
    '{"text":"Write a message. Type exit, quit, or bye to stop.",'
    '"value":{"prompt":"Write a message. Type exit, quit, or bye to stop.",'
    '"payload":null}}'
)


def _event(
    event_type: LogEventType,
    *,
    run_id: str = "run-1234",
    step_id: str | None = None,
    step_type: str | None = None,
    payload: LogEventPayload,
    event_id: str = "evt-1",
    sequence: int = 1,
) -> LogEvent:
    return LogEvent(
        sequence=sequence,
        event_id=event_id,
        run_id=run_id,
        event_type=event_type,
        step_id=step_id,
        step_type=step_type,
        agent_sequence=None,
        created_at="2026-05-12T10:30:15Z",
        payload=payload,
    )


def _output(text: str = "", value: dict[str, object] | None = None) -> OutputPayload:
    return OutputPayload(
        text=text,
        value=value,
        body_ref=None,
    )


def _output_from_json(raw: str) -> OutputPayload:
    if raw.endswith("..."):
        return _output(text=raw)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return _output(text=raw)
    if not isinstance(payload, dict):
        return _output(text=raw)
    text = payload.get("text")
    value = payload.get("value")
    return OutputPayload(
        text=text if isinstance(text, str) else raw,
        value=value if isinstance(value, dict) else None,
        body_ref=None,
    )


class FakeRunPort:
    def __init__(
        self,
        ack: CommandAck | RunDispatch | RuntimeError,
    ) -> None:
        self.ack = ack
        self.called_with: list[str] = []
        self.status_called_with: list[str] = []

    def run(self, raw_args: str) -> RunDispatch:
        self.called_with.append(raw_args)
        if isinstance(self.ack, RuntimeError):
            raise self.ack
        if isinstance(self.ack, RunDispatch):
            return self.ack
        if self.ack.status != CommandAckStatus.ACCEPTED:
            raise RuntimeError(self.ack.message)
        return RunDispatch(
            run_id=self.ack.run_id or "run-1234",
            status=RunRuntimeStatusKind.CREATED,
            worker_pid=3,
            error=RunDispatchError(
                kind=RunDispatchErrorKind.NONE,
                message="",
            ),
        )

    def status(self, run_id: str) -> RunRuntimeStatus | None:
        self.status_called_with.append(run_id)
        _ = run_id
        return None


class FakeWaitingPort:
    def __init__(self, ack: WaitingInputAck | None = None) -> None:
        self.ack = ack or WaitingInputAck(
            status=WaitingInputStatus.ACCEPTED,
            run_id="run-1234",
            message="",
        )
        self.called_with: list[tuple[str, str]] = []

    def send_input(self, *, run_id: str, text: str) -> WaitingInputAck:
        self.called_with.append((run_id, text))
        return self.ack


def attach_run_observer(
    viewmodel: ConsoleScreenViewModel,
    events_port: FakeEventsPort,
    run_id: str,
) -> None:
    events_port.subscribe(run_id=run_id, listener=viewmodel)


def test_console_screen_state_defaults_to_idle_main_session() -> None:
    state = ConsoleScreenState()

    assert state.session_key == "main"
    assert state.view_status.kind == ViewStatusKind.HIDDEN
    assert state.runs_table.visible is False
    assert state.runs_table.command == ""
    assert state.runs_table.rows == ()
    assert state.prompt.waiting_prompt == ""
    assert state.prompt.text == ""
    assert state.prompt.cursor_position == 0
    assert state.transcript.items == []
    assert state.autocompletion is None


def test_completion_state_exposes_selected_item() -> None:
    state = CompletionState(
        visible=True,
        query="/ru",
        items=(
            CompletionItem(label="runs"),
            CompletionItem(label="run"),
            CompletionItem(label="quit"),
        ),
        selected_index=1,
        replace_from=0,
        replace_to=3,
    )

    assert state.selected_item is not None
    assert state.selected_item.label == "run"


def test_inspect_run_context_emits_current_context() -> None:
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused")),
        waiting_port=FakeWaitingPort(),
    )
    viewmodel._run_event_context.activate_run(  # noqa: SLF001
        "run-1234",
        skill_name="ant",
        mode=RunMode.CHAT,
        status=RunStatus.WAITING_INPUT,
    )
    events = []
    viewmodel.bind_on_event(events.append)

    viewmodel.inspect_run_context()

    assert len(events) == 1
    assert events[0].run_id == "run-1234"
    assert events[0].skill_name == "ant"
    assert events[0].mode == RunMode.CHAT
    assert events[0].status == RunStatus.WAITING_INPUT


def test_interrupt_running_agent_turn_calls_agent_port_only_in_running_chat_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_to_thread(function, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return function(*args, **kwargs)

    monkeypatch.setattr(interrupt_agent_turn_use_case_module.asyncio, "to_thread", fake_to_thread)

    async def run() -> None:
        agent_port = FakeAgentPort(
            ack=CommandAck(status=CommandAckStatus.ACCEPTED, message="accepted")
        )
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused")),
            waiting_port=FakeWaitingPort(),
            agent_port=agent_port,
        )

        viewmodel._run_event_context.run_id = "run-1234"  # noqa: SLF001
        viewmodel._run_event_context.mode = RunMode.CHAT  # noqa: SLF001
        viewmodel._run_event_context.status = RunStatus.RUNNING  # noqa: SLF001

        interrupted = await viewmodel.interrupt_running_agent_turn()

        assert interrupted is True
        assert agent_port.called_with == ["run-1234"]

    asyncio.run(run())


def test_interrupt_running_agent_turn_ignores_non_chat_or_non_running_state() -> None:
    async def run() -> None:
        agent_port = FakeAgentPort(
            ack=CommandAck(status=CommandAckStatus.ACCEPTED, message="accepted")
        )
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused")),
            waiting_port=FakeWaitingPort(),
            agent_port=agent_port,
        )

        viewmodel._run_event_context.run_id = "run-1234"  # noqa: SLF001
        viewmodel._run_event_context.mode = RunMode.FLOW  # noqa: SLF001
        viewmodel._run_event_context.status = RunStatus.RUNNING  # noqa: SLF001

        interrupted = await viewmodel.interrupt_running_agent_turn()

        assert interrupted is False
        assert agent_port.called_with == []

    asyncio.run(run())


def test_interrupt_running_agent_turn_blocks_repeated_escape_while_ack_is_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    async def fake_to_thread(function, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        started.set()
        await release.wait()
        return function(*args, **kwargs)

    monkeypatch.setattr(interrupt_agent_turn_use_case_module.asyncio, "to_thread", fake_to_thread)

    async def run() -> None:
        agent_port = FakeAgentPort(
            ack=CommandAck(status=CommandAckStatus.ACCEPTED, message="accepted")
        )
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused")),
            waiting_port=FakeWaitingPort(),
            agent_port=agent_port,
        )

        viewmodel._run_event_context.run_id = "run-1234"  # noqa: SLF001
        viewmodel._run_event_context.mode = RunMode.CHAT  # noqa: SLF001
        viewmodel._run_event_context.status = RunStatus.RUNNING  # noqa: SLF001

        first_interrupt = asyncio.create_task(viewmodel.interrupt_running_agent_turn())
        await started.wait()

        assert viewmodel.state.prompt.mode == PromptMode.INTERRUPT_PENDING

        interrupted = await viewmodel.interrupt_running_agent_turn()

        assert interrupted is False
        assert agent_port.called_with == []

        release.set()
        assert await first_interrupt is True
        assert agent_port.called_with == ["run-1234"]
        assert viewmodel.state.prompt.mode == PromptMode.INTERRUPT_PENDING

    asyncio.run(run())


def test_prompt_change_populates_matching_commands() -> None:
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused")),
        waiting_port=FakeWaitingPort(),
    )

    viewmodel.prompt_change(text="/ru", cursor_position=3)

    assert viewmodel.state.autocompletion is not None
    assert viewmodel.state.autocompletion.visible is True
    assert [item.label for item in viewmodel.state.autocompletion.items] == ["run", "runs"]
    assert viewmodel.state.autocompletion.selected_item is not None
    assert viewmodel.state.autocompletion.selected_item.label == "run"


def test_notify_clears_interrupt_pending_when_run_leaves_running_chat() -> None:
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused")),
        waiting_port=FakeWaitingPort(),
    )
    viewmodel.state.prompt.mode = PromptMode.INTERRUPT_PENDING
    viewmodel._run_event_context.run_id = "run-1234"  # noqa: SLF001
    viewmodel._run_event_context.mode = RunMode.CHAT  # noqa: SLF001
    viewmodel._run_event_context.status = RunStatus.RUNNING  # noqa: SLF001

    viewmodel.notify(
        [
            _event(
                LogEventType.RUN_WAITING,
                step_type="wait_input",
                payload=RunWaitingPayload(output=_output_from_json(_WAITING_PROMPT_OUTPUT)),
                event_id="evt-1",
            )
        ]
    )

    assert viewmodel.state.prompt.mode == PromptMode.DEFAULT


def test_prompt_change_hides_non_matching_queries() -> None:
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused")),
        waiting_port=FakeWaitingPort(),
    )

    viewmodel.prompt_change(text="/xzx", cursor_position=4)

    assert viewmodel.state.autocompletion is None


def test_move_completion_updates_selected_index() -> None:
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused")),
        waiting_port=FakeWaitingPort(),
    )

    viewmodel.prompt_change(text="/ru", cursor_position=3)

    assert viewmodel.move_completion(1) is True
    assert viewmodel.state.autocompletion is not None
    assert viewmodel.state.autocompletion.selected_item is not None
    assert viewmodel.state.autocompletion.selected_item.label == "runs"


def test_prompt_enter_applies_completion_when_visible() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused")),
            waiting_port=FakeWaitingPort(),
        )

        viewmodel.prompt_change(text="/ru", cursor_position=3)
        viewmodel.move_completion(1)

        await viewmodel.prompt_enter()

        assert viewmodel.state.prompt.text == "/runs"
        assert viewmodel.state.prompt.cursor_position == 5
        assert viewmodel.state.autocompletion is None

    asyncio.run(run())


def test_prompt_enter_submits_when_completion_is_not_visible() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=FakeRunPort(
                CommandAck(
                    status=CommandAckStatus.ACCEPTED,
                    run_id="run-1234",
                    message="accepted",
                )
            ),
            waiting_port=FakeWaitingPort(),
        )

        viewmodel.prompt_change(text="/run chat", cursor_position=9)
        await viewmodel.prompt_enter()

        assert viewmodel.state.prompt.text == ""
        assert viewmodel.state.prompt.cursor_position == 0
        assert viewmodel.state.session_key == "run-1234"

    with patched_to_thread(
        run_command_use_case_module,
        submit_waiting_input_use_case_module,
    ):
        asyncio.run(run())


def test_console_screen_viewmodel_requests_exit_for_quit() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=FakeRunPort(
                CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"),
            ),
            waiting_port=FakeWaitingPort(),
        )

        await viewmodel.submit("/quit")

        assert viewmodel.state.transcript.items == []

    asyncio.run(run())


def test_console_screen_viewmodel_dispatches_run() -> None:
    run_port = FakeRunPort(
        CommandAck(
            status=CommandAckStatus.ACCEPTED,
            run_id="run-1234",
            message="[run-dispatch] chat:1234\n  ↳ created",
        )
    )

    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=run_port,
            waiting_port=FakeWaitingPort(),
        )

        await viewmodel.submit("/run chat")

        assert run_port.called_with == ["chat"]
        assert len(viewmodel.state.transcript.items) == 1
        assert isinstance(viewmodel.state.transcript.items[0], RunAckItem)
        assert viewmodel.state.transcript.items[0].skill == "chat"
        assert viewmodel.state.transcript.items[0].run_id == "run-1234"
        assert viewmodel.state.view_status.kind == ViewStatusKind.RUNNING
        assert viewmodel.state.session_key == "run-1234"
        assert viewmodel.state.prompt.text == ""
        assert viewmodel.state.prompt.cursor_position == 0

    with patched_to_thread(run_command_use_case_module):
        asyncio.run(run())


def test_console_screen_viewmodel_opens_runs_table_for_runs_command() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused")),
            waiting_port=FakeWaitingPort(),
            runs_port=FakeRunsPort(),
        )

        await viewmodel.submit("/runs")

        assert viewmodel.state.runs_table.visible is True
        assert viewmodel.state.view_status.kind == ViewStatusKind.HIDDEN
        assert isinstance(viewmodel.state.transcript.items[0], UserInputItem)
        assert viewmodel.state.transcript.items[0].text == "/runs"
        assert [item.id for item in viewmodel.state.runs_table.rows] == ["run-1"]

    with patched_to_thread(list_runs_use_case_module):
        asyncio.run(run())


def test_console_screen_viewmodel_opens_runs_table_with_filters() -> None:
    async def run() -> None:
        runs_port = FakeRunsPort()
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused")),
            waiting_port=FakeWaitingPort(),
            runs_port=runs_port,
        )

        await viewmodel.submit("/runs waiting")

        assert runs_port.called_with == [(20, ["waiting"])]
        assert viewmodel.state.runs_table.visible is True
        assert viewmodel.state.view_status.kind == ViewStatusKind.HIDDEN
        assert [item.id for item in viewmodel.state.runs_table.rows] == ["run-1"]

    with patched_to_thread(list_runs_use_case_module):
        asyncio.run(run())


def test_console_screen_viewmodel_opens_chats_table_for_waiting_input_runs() -> None:
    async def run() -> None:
        runs_port = FakeRunsPort(
            runs=[
                make_runs_port_item(run_id="run-input", wait_type="input"),
                make_runs_port_item(
                    run_id="run-webhook",
                    current="wait_signal",
                    wait_type="webhook",
                ),
            ]
        )
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused")),
            waiting_port=FakeWaitingPort(),
            runs_port=runs_port,
        )

        await viewmodel.submit("/chats")

        assert runs_port.called_with == [(20, ["WAITING"])]
        assert viewmodel.state.runs_table.visible is True
        assert viewmodel.state.runs_table.command == "/chats"
        assert [item.id for item in viewmodel.state.runs_table.rows] == ["run-input"]

    with patched_to_thread(list_runs_use_case_module):
        asyncio.run(run())


def test_console_screen_viewmodel_maps_runs_errors() -> None:
    class FailingRunsPort:
        def list_runs(
            self,
            *,
            limit: int = 20,
            statuses: list[str] | None = None,
        ) -> list[RunsPortItem]:
            _ = limit
            _ = statuses
            raise RuntimeError("runs command failed")

    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused")),
            waiting_port=FakeWaitingPort(),
            runs_port=FailingRunsPort(),
        )

        await viewmodel.submit("/runs")

        assert viewmodel.state.runs_table.visible is False
        assert viewmodel.state.view_status.kind == ViewStatusKind.ERROR
        assert isinstance(viewmodel.state.transcript.items[0], UserInputItem)
        assert isinstance(viewmodel.state.transcript.items[1], DispatchErrorItem)

    with patched_to_thread(list_runs_use_case_module):
        asyncio.run(run())


def test_console_screen_viewmodel_rejects_plain_text() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=FakeRunPort(
                CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"),
            ),
            waiting_port=FakeWaitingPort(),
        )

        await viewmodel.submit("hola")

        assert isinstance(viewmodel.state.transcript.items[0], UserInputItem)
        assert isinstance(viewmodel.state.transcript.items[1], InfoItem)
        assert (
            viewmodel.state.transcript.items[1].text
            == "Use /run <agent> to execute an agent."
        )
        assert viewmodel.state.view_status.kind == ViewStatusKind.HIDDEN
        assert viewmodel.state.prompt.text == ""
        assert viewmodel.state.prompt.cursor_position == 0

    asyncio.run(run())


def test_console_screen_viewmodel_maps_dispatch_error() -> None:
    run_port = FakeRunPort(
        RunDispatch(
            run_id="",
            status=RunRuntimeStatusKind.FAILED,
            worker_pid=0,
            error=RunDispatchError(
                kind=RunDispatchErrorKind.RUN_NOT_FOUND,
                message="agent not found: missing_skill",
            )
        )
    )

    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=run_port,
            waiting_port=FakeWaitingPort(),
        )

        await viewmodel.submit("/run missing_skill")

        assert isinstance(viewmodel.state.transcript.items[1], DispatchErrorItem)
        assert (
            viewmodel.state.transcript.items[1].message
            == "error: agent not found: missing_skill"
        )
        assert viewmodel.state.view_status.kind == ViewStatusKind.ERROR
        assert viewmodel.state.session_key == "main"

    with patched_to_thread(run_command_use_case_module):
        asyncio.run(run())


def test_console_screen_viewmodel_subscribes_and_applies_log_events() -> None:
    run_port = FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"))
    events_port = FakeEventsPort()
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=run_port,
        events_port=events_port,
        waiting_port=FakeWaitingPort(),
    )

    attach_run_observer(viewmodel, events_port, "run-1234")
    viewmodel.notify([
        _event(
            LogEventType.STEP_STARTED,
            step_id="show_message",
            step_type="notify",
            payload=StepStartedPayload(),
            event_id="evt-1",
        ),
        _event(
            LogEventType.RUN_FINISHED,
            payload=RunFinishedPayload(status="SUCCEEDED"),
            event_id="evt-2",
            sequence=2,
        ),
    ])

    assert events_port.subscribe_calls == ["run-1234"]
    assert viewmodel.state.view_status.kind == ViewStatusKind.HIDDEN
    assert isinstance(viewmodel.state.transcript.items[0], RunStepItem)
    assert isinstance(viewmodel.state.transcript.items[1], RunStatusItem)
    assert viewmodel.state.transcript.items[0].step_id == "show_message"
    assert viewmodel.state.transcript.items[0].step_type == "notify"
    assert viewmodel.state.transcript.items[1].status == "succeeded"


def test_console_screen_viewmodel_sends_plain_text_when_waiting_for_input() -> None:
    run_port = FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"))
    waiting_port = FakeWaitingPort(
        WaitingInputAck(
            status=WaitingInputStatus.ACCEPTED,
            run_id="run-1234",
            message="",
        )
    )

    async def run() -> None:
        events_port = FakeEventsPort()
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=run_port,
            events_port=events_port,
            waiting_port=waiting_port,
        )
        attach_run_observer(viewmodel, events_port, "run-1234")
        viewmodel._run_event_context.activate_run(  # noqa: SLF001
            "run-1234",
            skill_name="run-1234",
            mode=RunMode.FLOW,
            status=RunStatus.RUNNING,
        )
        viewmodel.notify(
            [
                _event(
                    LogEventType.RUN_WAITING,
                    step_type="wait_input",
                    payload=RunWaitingPayload(
                        output=_output("Write a message. Type exit, quit, or bye to stop.")
                    ),
                )
            ]
        )

        await viewmodel.submit("hello world")

        assert waiting_port.called_with == [("run-1234", "hello world")]
        assert isinstance(viewmodel.state.transcript.items[-1], RunResumeItem)
        assert viewmodel.state.transcript.items[-1].run_id == "run-1234"
        assert viewmodel.state.transcript.items[-1].skill == "run-1234"
        assert viewmodel.state.view_status.kind == ViewStatusKind.RUNNING
        assert viewmodel.state.prompt.waiting_prompt == ""
        assert viewmodel.state.prompt.text == ""
        assert viewmodel.state.prompt.cursor_position == 0

    with patched_to_thread(submit_waiting_input_use_case_module):
        asyncio.run(run())


def test_console_screen_viewmodel_does_not_send_plain_text_when_waiting_not_input() -> None:
    run_port = FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"))
    events_port = FakeEventsPort()
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=run_port,
        events_port=events_port,
        waiting_port=FakeWaitingPort(),
    )
    attach_run_observer(viewmodel, events_port, "run-1234")
    viewmodel.notify(
        [
            _event(
                LogEventType.RUN_WAITING,
                step_type="wait_webhook",
                payload=RunWaitingPayload(output=_output()),
            )
        ]
    )

    async def run() -> None:
        await viewmodel.submit("hola")

    asyncio.run(run())

    assert isinstance(viewmodel.state.transcript.items[-1], InfoItem)


def test_console_screen_viewmodel_maps_waiting_input_rejection() -> None:
    run_port = FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"))
    waiting_port = FakeWaitingPort(
        WaitingInputAck(
            status=WaitingInputStatus.REJECTED,
            run_id="run-1234",
            message="error: input rejected",
        )
    )

    async def run() -> None:
        events_port = FakeEventsPort()
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=run_port,
            events_port=events_port,
            waiting_port=waiting_port,
        )
        attach_run_observer(viewmodel, events_port, "run-1234")
        viewmodel._run_event_context.activate_run(  # noqa: SLF001
            "run-1234",
            skill_name="run-1234",
            mode=RunMode.CHAT,
            status=RunStatus.RUNNING,
        )
        viewmodel.notify(
            [
                _event(
                    LogEventType.RUN_WAITING,
                    step_type="wait_input",
                    payload=RunWaitingPayload(output=_output()),
                )
            ]
        )

        await viewmodel.submit("hello")

        assert waiting_port.called_with == [("run-1234", "hello")]
        assert isinstance(viewmodel.state.transcript.items[-1], DispatchErrorItem)
        assert viewmodel.state.view_status.kind == ViewStatusKind.ERROR
        assert viewmodel.state.prompt.text == ""
        assert viewmodel.state.prompt.cursor_position == 0

    with patched_to_thread(submit_waiting_input_use_case_module):
        asyncio.run(run())


def test_console_screen_viewmodel_does_not_infer_waiting_input_without_run_waiting_step_type(
) -> None:
    run_port = FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"))
    waiting_port = FakeWaitingPort(
        WaitingInputAck(
            status=WaitingInputStatus.ACCEPTED,
            run_id="run-1234",
            message="",
        )
    )

    async def run() -> None:
        events_port = FakeEventsPort()
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=run_port,
            events_port=events_port,
            waiting_port=waiting_port,
        )
        attach_run_observer(viewmodel, events_port, "run-1234")
        viewmodel._run_event_context.activate_run(  # noqa: SLF001
            "run-1234",
            skill_name="run-1234",
            mode=RunMode.CHAT,
            status=RunStatus.RUNNING,
        )
        viewmodel.notify(
            [
                _event(
                    LogEventType.STEP_STARTED,
                    step_id="ask_user",
                    step_type="wait_input",
                    payload=StepStartedPayload(),
                ),
                _event(
                    LogEventType.RUN_WAITING,
                    step_id="ask_user",
                    step_type="",
                    payload=RunWaitingPayload(output=_output("Write a short summary")),
                    event_id="evt-2",
                    sequence=2,
                ),
            ]
        )
        assert viewmodel.state.prompt.waiting_prompt == ""
        assert viewmodel._run_event_context.status == RunStatus.WAITING_WEBHOOK  # noqa: SLF001

        await viewmodel.submit("hola mundo")

        assert waiting_port.called_with == []
        outputs = [
            item for item in viewmodel.state.transcript.items if isinstance(item, RunOutputItem)
        ]
        waiting_items = [
            item
            for item in viewmodel.state.transcript.items
            if isinstance(item, RunWaitingInputItem)
        ]
        assert outputs == []
        assert waiting_items == []
        assert viewmodel.state.prompt.waiting_prompt == ""

    with patched_to_thread(submit_waiting_input_use_case_module):
        asyncio.run(run())


def test_console_screen_viewmodel_uses_skill_name_on_resume_after_wait_input() -> None:
    run_port = FakeRunPort(
        CommandAck(
            status=CommandAckStatus.ACCEPTED,
            run_id="run-1234",
            message="unused",
        )
    )
    waiting_port = FakeWaitingPort(
        WaitingInputAck(
            status=WaitingInputStatus.ACCEPTED,
            run_id="run-1234",
            message="",
        )
    )

    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=run_port,
            waiting_port=waiting_port,
        )
        await viewmodel.submit("/run wait_input_test")
        viewmodel.notify(
            [
                _event(
                    LogEventType.RUN_WAITING,
                    step_type="wait_input",
                    payload=RunWaitingPayload(output=_output()),
                ),
            ]
        )

        await viewmodel.submit("hola mundo")

        last_item = viewmodel.state.transcript.items[-1]
        assert isinstance(last_item, RunResumeItem)
        assert last_item.run_id == "run-1234"
        assert last_item.skill == "wait_input_test"
        assert viewmodel.state.prompt.text == ""
        assert viewmodel.state.prompt.cursor_position == 0

    with patched_to_thread(
        run_command_use_case_module,
        submit_waiting_input_use_case_module,
    ):
        asyncio.run(run())


def test_console_screen_viewmodel_reconstructs_input_received_and_ignores_run_resume() -> None:
    run_port = FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"))
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=run_port,
        waiting_port=FakeWaitingPort(),
    )

    viewmodel.notify(
        [
            _event(
                LogEventType.INPUT_RECEIVED,
                payload=InputReceivedPayload(payload={"text": "hola"}),
                event_id="evt-1",
            ),
            _event(
                LogEventType.RUN_RESUME,
                payload=RunResumePayload(source="manual"),
                event_id="evt-2",
                sequence=2,
            ),
        ]
    )

    assert len(viewmodel.state.transcript.items) == 1
    assert isinstance(viewmodel.state.transcript.items[0], UserInputItem)
    assert viewmodel.state.transcript.items[0].text == "hola"


def test_console_screen_viewmodel_renders_waiting_event_output() -> None:
    run_port = FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"))
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=run_port,
        waiting_port=FakeWaitingPort(),
    )

    first_batch = [
        _event(
            LogEventType.RUN_WAITING,
            step_id="ask_user",
            step_type="wait_input",
            payload=RunWaitingPayload(output=_output("Write a short summary")),
            event_id="evt-wait-1",
        )
    ]
    replay_batch = [
        _event(
            LogEventType.RUN_WAITING,
            step_id="ask_user",
            step_type="wait_input",
            payload=RunWaitingPayload(output=_output("Write a short summary")),
            event_id="evt-wait-1",
        )
    ]

    viewmodel.notify(first_batch)
    viewmodel.notify(replay_batch)

    outputs = [
        item for item in viewmodel.state.transcript.items if isinstance(item, RunOutputItem)
    ]
    waiting_items = [
        item
        for item in viewmodel.state.transcript.items
        if isinstance(item, RunWaitingInputItem)
    ]
    assert outputs == []
    assert len(waiting_items) == 1
    assert waiting_items[0].prompt == "Write a short summary"
    assert viewmodel.state.prompt.waiting_prompt == "Write a short summary"


def test_console_screen_viewmodel_skips_input_received_wait_output_block() -> None:
    run_port = FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"))
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=run_port,
        waiting_port=FakeWaitingPort(),
    )

    viewmodel.notify(
        [
            _event(
                LogEventType.RUN_WAITING,
                step_id="ask_user",
                step_type="wait_input",
                payload=RunWaitingPayload(output=_output_from_json(_INPUT_RECEIVED_OUTPUT)),
                event_id="evt-wait-input-received",
            )
        ]
    )

    outputs = [
        item for item in viewmodel.state.transcript.items if isinstance(item, RunOutputItem)
    ]
    waiting_items = [
        item
        for item in viewmodel.state.transcript.items
        if isinstance(item, RunWaitingInputItem)
    ]
    assert outputs == []
    assert len(waiting_items) == 1
    assert waiting_items[0].prompt == "Input received."


def test_console_screen_viewmodel_renders_wait_input_steps_as_received() -> None:
    run_port = FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"))
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=run_port,
        waiting_port=FakeWaitingPort(),
    )

    viewmodel.notify(
        [
            _event(
                LogEventType.STEP_STARTED,
                step_id="ask_user",
                step_type="wait_input",
                payload=StepStartedPayload(),
                event_id="evt-step-1",
            ),
            _event(
                LogEventType.STEP_STARTED,
                step_id="ask_user",
                step_type="wait_input",
                payload=StepStartedPayload(),
                event_id="evt-step-2",
                sequence=2,
            ),
        ]
    )

    steps = [item for item in viewmodel.state.transcript.items if isinstance(item, RunStepItem)]
    assert len(steps) == 2


def test_console_screen_viewmodel_skips_step_success_wait_input_input_received_output() -> None:
    run_port = FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"))
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=run_port,
        waiting_port=FakeWaitingPort(),
    )

    viewmodel.notify(
        [
                _event(
                    LogEventType.STEP_SUCCESS,
                    step_id="ask_user",
                    step_type="wait_input",
                    payload=StepSuccessPayload(
                        output=_output(
                            "Input received.",
                            value={"payload": {"text": "hola mundo loca"}},
                        )
                    ),
                    event_id="evt-step-success-input-received",
                )
        ]
    )

    outputs = [
        item for item in viewmodel.state.transcript.items if isinstance(item, RunOutputItem)
    ]
    assert outputs == []


def test_console_screen_viewmodel_maps_output_format_by_step_type() -> None:
    run_port = FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"))
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=run_port,
        waiting_port=FakeWaitingPort(),
    )

    viewmodel.notify(
        [
            _event(
                LogEventType.STEP_SUCCESS,
                step_id="support_agent",
                step_type="agent",
                payload=StepSuccessPayload(output=_output_from_json('{"text":"hola"}')),
                event_id="evt-agent-out",
            ),
            _event(
                LogEventType.STEP_SUCCESS,
                step_id="run_check",
                step_type="shell",
                payload=StepSuccessPayload(output=_output_from_json('{"value":{"ok":true}}')),
                event_id="evt-shell-out",
                sequence=2,
            ),
        ]
    )

    outputs = [
        item for item in viewmodel.state.transcript.items if isinstance(item, RunOutputItem)
    ]
    agent_messages = [
        item
        for item in viewmodel.state.transcript.items
        if isinstance(item, AgentAssistantMessageItem)
    ]
    assert len(agent_messages) == 1
    assert agent_messages[0].message_type == "final"
    assert agent_messages[0].text == "hola"
    assert len(outputs) == 1
    assert outputs[0].format == OutputFormat.STRUCTURED


def test_console_screen_viewmodel_appends_agent_tool_call_and_result_items() -> None:
    run_port = FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"))
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=run_port,
        waiting_port=FakeWaitingPort(),
    )

    viewmodel.notify(
        [
            _event(
                LogEventType.AGENT_TOOL_CALL,
                step_id="support_agent",
                step_type="agent",
                payload=AgentToolCallPayload(
                    type="tool_call",
                    turn_id="turn-1",
                    parent_sequence=None,
                    tool_call_id="call-1",
                    tool="shell",
                    args={"command": "git status --short"},
                ),
                event_id="evt-agent-tool-call",
            ),
            _event(
                LogEventType.AGENT_TOOL_RESULT,
                step_id="support_agent",
                step_type="agent",
                payload=AgentToolResultPayload(
                    type="tool_result",
                    turn_id="turn-1",
                    parent_sequence=None,
                    tool_call_id="call-1",
                    tool="shell",
                    status=AgentToolResultStatus.COMPLETED,
                    data={"ok": True},
                    text="M docs/configuration.md",
                    error=None,
                ),
                event_id="evt-agent-tool-result",
                sequence=2,
            ),
        ]
    )

    assert isinstance(viewmodel.state.transcript.items[0], AgentToolCallItem)
    assert viewmodel.state.transcript.items[0].command == "git status --short"
    assert isinstance(viewmodel.state.transcript.items[1], AgentToolResultItem)
    assert viewmodel.state.transcript.items[1].preview == "M docs/configuration.md"


def test_console_screen_viewmodel_appends_agent_assistant_message_item() -> None:
    run_port = FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"))
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=run_port,
        waiting_port=FakeWaitingPort(),
    )

    viewmodel.notify(
        [
            _event(
                LogEventType.AGENT_ASSISTANT_MESSAGE,
                step_id="support_agent",
                step_type="agent",
                payload=AgentAssistantMessagePayload(
                    type="assistant_message",
                    turn_id="turn-1",
                    message_type=AgentAssistantMessageType.TOOL_CALLS,
                    text="I will inspect the repository state.",
                ),
                event_id="evt-agent-assistant",
            ),
        ]
    )

    assert isinstance(viewmodel.state.transcript.items[0], AgentAssistantMessageItem)
    assert viewmodel.state.transcript.items[0].message_type == "tool_calls"
    assert viewmodel.state.transcript.items[0].text == "I will inspect the repository state."


def test_console_screen_viewmodel_uses_step_success_as_only_agent_final_output() -> None:
    run_port = FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"))
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=run_port,
        waiting_port=FakeWaitingPort(),
    )

    viewmodel.notify(
        [
            _event(
                LogEventType.AGENT_ASSISTANT_MESSAGE,
                step_id="support_agent",
                step_type="agent",
                payload=AgentAssistantMessagePayload(
                    type="assistant_message",
                    turn_id="turn-1",
                    message_type=AgentAssistantMessageType.FINAL,
                    text="Hecho truncado...",
                ),
                event_id="evt-agent-final",
            ),
            _event(
                LogEventType.STEP_SUCCESS,
                step_id="support_agent",
                step_type="agent",
                payload=StepSuccessPayload(
                    output=_output_from_json('{"text":"Hecho completo."}')
                ),
                event_id="evt-agent-step-success",
                sequence=2,
            ),
        ]
    )

    assert len(viewmodel.state.transcript.items) == 1
    assert isinstance(viewmodel.state.transcript.items[0], AgentAssistantMessageItem)
    assert viewmodel.state.transcript.items[0].message_type == "final"
    assert viewmodel.state.transcript.items[0].text == "Hecho completo."


def test_console_screen_viewmodel_moves_wait_prompt_to_status_instead_of_transcript_output(
) -> None:
    run_port = FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"))
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=run_port,
        waiting_port=FakeWaitingPort(),
    )

    viewmodel.notify(
        [
            _event(
                LogEventType.RUN_WAITING,
                step_id="ask_user",
                step_type="wait_input",
                payload=RunWaitingPayload(output=_output_from_json(_WAITING_PROMPT_OUTPUT)),
                event_id="evt-wait-2",
            )
        ]
    )

    outputs = [
        item for item in viewmodel.state.transcript.items if isinstance(item, RunOutputItem)
    ]
    waiting_items = [
        item
        for item in viewmodel.state.transcript.items
        if isinstance(item, RunWaitingInputItem)
    ]
    assert outputs == []
    assert len(waiting_items) == 1
    assert waiting_items[0].prompt == "Write a message. Type exit, quit, or bye to stop."
    assert (
        viewmodel.state.prompt.waiting_prompt
        == "Write a message. Type exit, quit, or bye to stop."
    )
