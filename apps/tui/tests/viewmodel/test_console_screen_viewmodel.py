from __future__ import annotations

import asyncio

import pytest

import stui.usecase.list_models_use_case as list_models_use_case_module
import stui.usecase.list_runs_use_case as list_runs_use_case_module
import stui.usecase.run_command_use_case as run_command_use_case_module
import stui.usecase.select_model_use_case as select_model_use_case_module
from apps.tui.tests.support import (
    FakeAgentPort,
    FakeEventsPort,
    FakeModelsPort,
    FakeRunsPort,
    build_viewmodel,
    patched_to_thread,
)
from stui.di.strings import TuiStrings
from stui.port.agent_port import (
    AgentContextStats,
    AgentContextWindowStats,
    AgentStatsResult,
    AgentStatsStatus,
)
from stui.port.event_models import (
    ActionOpenUrlValue,
    ActionRunValue,
    AgentOutputValue,
    LogEvent,
    LogEventPayload,
    LogEventType,
    NotifyActionValue,
    OutputPayload,
    RunFinishedPayload,
    RunWaitingPayload,
    StepStartedPayload,
    StepSuccessPayload,
    WaitInputOutputValue,
    WaitWebhookOutputValue,
)
from stui.port.models_port import ModelsPortModelItem, ModelsPortProviderItem
from stui.port.notify_action_port import (
    NotifyActionAck,
    NotifyActionAckStatus,
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
    refresh_agent_context_stats_use_case as refresh_agent_context_stats_use_case_module,
)
from stui.usecase import (
    submit_waiting_input_use_case as submit_waiting_input_use_case_module,
)
from stui.usecase.done_notify_action_use_case import DoneNotifyActionResult
from stui.usecase.open_notify_action_use_case import OpenNotifyActionResult
from stui.usecase.run_event_context import RunMode, RunStatus
from stui.viewmodel.console_screen_state import (
    ActionOpenUrlItem,
    AgentContextStatsState,
    CompletionItem,
    CompletionState,
    ConsoleScreenState,
    DispatchErrorItem,
    InfoItem,
    NotifyActionState,
    PromptMode,
    RunFinishedItem,
    RunOutputItem,
    RunResumeItem,
    RunStepItem,
    RunWaitingInputItem,
    StepOutputItem,
    UserInputItem,
    ViewStatusKind,
)
from stui.viewmodel.console_screen_viewmodel import ConsoleScreenViewModel

pytestmark = pytest.mark.unit

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


def _output(
    text: str = "",
    value: WaitInputOutputValue | None = None,
) -> OutputPayload:
    return OutputPayload(
        text=text,
        value=value,
        body_ref=None,
    )


def _waiting_output(prompt: str = "") -> OutputPayload:
    return OutputPayload(
        text=prompt,
        value=WaitInputOutputValue(prompt=prompt),
        body_ref=None,
    )


def _waiting_webhook_output() -> OutputPayload:
    return OutputPayload(
        text="",
        value=WaitWebhookOutputValue(
            webhook="example-auth",
            key="GrbyVerTlIkPm33R-DbTe_7h3WKNbKkl",
        ),
        body_ref=None,
    )


def _agent_output(text: str) -> OutputPayload:
    return OutputPayload(
        text=text,
        value=AgentOutputValue(
            data={
                "final": text,
                "stop_reason": "final",
            }
        ),
        body_ref=None,
    )


class FakeRunPort:
    def __init__(
        self,
        ack: CommandAck | RunDispatch | RuntimeError,
        events: list[str] | None = None,
    ) -> None:
        self.ack = ack
        self.events = events
        self.called_with: list[str] = []
        self.status_called_with: list[str] = []

    def run(self, raw_args: str) -> RunDispatch:
        if self.events is not None:
            self.events.append("run")
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


class FakeNotifyActionPort:
    def __init__(self, events: list[str] | None = None) -> None:
        self.events = events
        self.open_calls: list[tuple[str, str, str]] = []
        self.done_calls: list[tuple[str, str]] = []

    def open(self, *, run_id: str, action_uid: str, url: str) -> NotifyActionAck:
        self.open_calls.append((run_id, action_uid, url))
        return NotifyActionAck(
            status=NotifyActionAckStatus.ACCEPTED,
            run_id=run_id,
            action_uid=action_uid,
        )

    def done(self, *, run_id: str, action_uid: str) -> NotifyActionAck:
        if self.events is not None:
            self.events.append("done")
        self.done_calls.append((run_id, action_uid))
        return NotifyActionAck(
            status=NotifyActionAckStatus.ACCEPTED,
            run_id=run_id,
            action_uid=action_uid,
        )


class _FakeOpenNotifyActionUseCase:
    def __init__(self) -> None:
        self.called_with: list[tuple[str, str, str]] = []

    def execute(
        self,
        *,
        state: ConsoleScreenState,
        run_id: str,
        action_uid: str,
        url: str,
    ) -> OpenNotifyActionResult:
        self.called_with.append((run_id, action_uid, url))
        return OpenNotifyActionResult(state=state)


class _FakeDoneNotifyActionUseCase:
    def __init__(self) -> None:
        self.called_with: list[tuple[str, str]] = []

    def execute(
        self,
        *,
        state: ConsoleScreenState,
        run_id: str,
        action_uid: str,
    ) -> DoneNotifyActionResult:
        self.called_with.append((run_id, action_uid))
        return DoneNotifyActionResult(state=state)


def attach_run_observer(
    viewmodel: ConsoleScreenViewModel,
    events_port: FakeEventsPort,
    run_id: str,
) -> None:
    events_port.subscribe(run_id=run_id, listener=viewmodel)


def test_console_screen_state_defaults_to_idle_main_session() -> None:
    state = ConsoleScreenState()

    assert state.session_key == "main"
    assert state.run_name == ""
    assert state.view_status.kind == ViewStatusKind.HIDDEN
    assert state.runs_table.visible is False
    assert state.runs_table.command == ""
    assert state.runs_table.rows == ()
    assert state.prompt.waiting_prompt == ""
    assert state.prompt.text == ""
    assert state.prompt.cursor_position == 0
    assert state.transcript.items == []
    assert state.autocompletion is None
    assert state.agent_context_stats is None


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
        run_name="ant",
        status=RunStatus.WAITING_INPUT,
    )
    events = []
    viewmodel.bind_on_event(events.append)

    viewmodel.inspect_run_context()

    assert len(events) == 1
    assert events[0].run_id == "run-1234"
    assert events[0].run_name == "ant"
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


def test_prompt_change_hides_runs_table_when_autocomplete_appears() -> None:
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused")),
        waiting_port=FakeWaitingPort(),
    )
    viewmodel.state.runs_table.visible = True
    viewmodel.state.runs_table.command = "/runs"
    viewmodel.state.set_agent_context_stats(
        AgentContextStatsState(
            entries=24,
            estimated_tokens=2618,
            start_sequence=1,
            end_sequence=24,
            current_tokens=2618,
            limit_tokens=80000,
            capacity_tokens=100000,
        )
    )

    viewmodel.prompt_change(text="/", cursor_position=1)

    assert viewmodel.state.autocompletion is not None
    assert viewmodel.state.autocompletion.visible is True
    assert viewmodel.state.runs_table.visible is False
    assert viewmodel.state.runs_table.command == ""
    assert viewmodel.state.agent_context_stats is None
    assert viewmodel.state.prompt.mode == PromptMode.AUTOCOMPLETION


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
                payload=RunWaitingPayload(
                    output=_waiting_output(
                        "Write a message. Type exit, quit, or bye to stop."
                    )
                ),
                event_id="evt-1",
            )
        ]
    )

    assert viewmodel.state.prompt.mode == PromptMode.DEFAULT


def test_notify_projects_pending_notify_action_to_screen_state() -> None:
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused")),
        waiting_port=FakeWaitingPort(),
    )

    viewmodel.notify(
        [
            _event(
                LogEventType.STEP_SUCCESS,
                step_id="auth_link",
                step_type="notify",
                payload=StepSuccessPayload(
                    output=OutputPayload(
                        text="Authorize the app",
                        value=NotifyActionValue(
                            message="Authorize the app",
                            action=ActionOpenUrlValue(
                                uid="action-open-1",
                                type="open_url",
                                label="Open authorization",
                                message="Open the authorization link.",
                                url="https://example.com/oauth/start",
                            ),
                        ),
                        body_ref=None,
                    )
                ),
            )
        ]
    )

    assert viewmodel.state.notify_action == NotifyActionState(
        run_id="run-1234",
        message="Open the authorization link.",
        action=ActionOpenUrlItem(
            uid="action-open-1",
            type="open_url",
            label="Open authorization",
            message="Open the authorization link.",
            url="https://example.com/oauth/start",
        ),
    )


def test_notify_updates_agent_status_context() -> None:
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused")),
        waiting_port=FakeWaitingPort(),
    )

    viewmodel.notify(
        [
            _event(
                LogEventType.STEP_STARTED,
                step_id="support_agent",
                step_type="agent",
                payload=StepStartedPayload(),
            )
        ]
    )

    assert viewmodel._run_event_context.agent_id == "support_agent"  # noqa: SLF001


def test_notify_refreshes_visible_agent_context_stats() -> None:
    async def run() -> None:
        agent_port = FakeAgentPort(
            stats=AgentStatsResult(
                status=AgentStatsStatus.OK,
                run_id="run-1234",
                agent_id="support_agent",
                context_id="ctx-1234",
                context=AgentContextStats(
                    entries=1001,
                    estimated_tokens=4000,
                    window=AgentContextWindowStats(
                        start_sequence=100,
                        end_sequence=1100,
                        current_tokens=4000,
                        limit_tokens=80000,
                        capacity_tokens=100000,
                    ),
                ),
            )
        )
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused")),
            waiting_port=FakeWaitingPort(),
            agent_port=agent_port,
        )
        viewmodel._run_event_context.run_id = "run-1234"  # noqa: SLF001
        viewmodel._run_event_context.agent_id = "support_agent"  # noqa: SLF001
        viewmodel.state.set_agent_context_stats(
            AgentContextStatsState(
                entries=24,
                estimated_tokens=2618,
                start_sequence=1,
                end_sequence=24,
                current_tokens=2618,
                limit_tokens=80000,
                capacity_tokens=100000,
            )
        )

        viewmodel.notify(
            [
                _event(
                    LogEventType.STEP_STARTED,
                    step_id="support_agent",
                    step_type="agent",
                    payload=StepStartedPayload(),
                )
            ]
        )
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert agent_port.stats_called_with == [("run-1234", "support_agent")]
        assert viewmodel.state.agent_context_stats == AgentContextStatsState(
            entries=1001,
            estimated_tokens=4000,
            start_sequence=100,
            end_sequence=1100,
            current_tokens=4000,
            limit_tokens=80000,
            capacity_tokens=100000,
        )

    with patched_to_thread(refresh_agent_context_stats_use_case_module):
        asyncio.run(run())


def test_open_notify_action_link_calls_use_case() -> None:
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused")),
        waiting_port=FakeWaitingPort(),
    )
    use_case = _FakeOpenNotifyActionUseCase()
    object.__setattr__(viewmodel._use_cases, "open_notify_action", use_case)  # noqa: SLF001

    viewmodel.open_notify_action_link(
        run_id="run-1",
        action_uid="action-open-1",
        url="https://example.com/oauth/start",
    )

    assert use_case.called_with == [
        ("run-1", "action-open-1", "https://example.com/oauth/start"),
    ]


def test_done_notify_action_calls_use_case() -> None:
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused")),
        waiting_port=FakeWaitingPort(),
    )
    use_case = _FakeDoneNotifyActionUseCase()
    object.__setattr__(viewmodel._use_cases, "done_notify_action", use_case)  # noqa: SLF001

    viewmodel.done_notify_action(
        run_id="run-1",
        action_uid="action-open-1",
    )

    assert use_case.called_with == [("run-1", "action-open-1")]


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
        runs_port = FakeRunsPort()
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused")),
            waiting_port=FakeWaitingPort(),
            runs_port=runs_port,
        )

        viewmodel.prompt_change(text="/ru", cursor_position=3)
        viewmodel.move_completion(1)

        await viewmodel.prompt_enter()

        assert runs_port.called_with == [(20, [])]
        assert viewmodel.state.runs_table.visible is True
        assert viewmodel.state.prompt.text == ""
        assert viewmodel.state.prompt.cursor_position == 0
        assert viewmodel.state.autocompletion is None

    with patched_to_thread(list_runs_use_case_module):
        asyncio.run(run())


def test_prompt_enter_applies_auth_command_completion_and_shows_params() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused")),
            waiting_port=FakeWaitingPort(),
        )

        viewmodel.prompt_change(text="/a", cursor_position=2)

        await viewmodel.prompt_enter()

        assert viewmodel.state.prompt.text == "/auth "
        assert viewmodel.state.prompt.cursor_position == 6
        assert viewmodel.state.autocompletion is not None
        assert [item.label for item in viewmodel.state.autocompletion.items] == [
            "codex",
            "minimax",
            "bedrock",
        ]

    asyncio.run(run())


def test_prompt_enter_submits_auth_param_completion_when_visible() -> None:
    run_port = FakeRunPort(
        CommandAck(
            status=CommandAckStatus.ACCEPTED,
            run_id="run-codex",
            message="created",
        )
    )

    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=run_port,
            waiting_port=FakeWaitingPort(),
        )

        viewmodel.prompt_change(text="/auth c", cursor_position=7)

        await viewmodel.prompt_enter()

        assert run_port.called_with == ["auths/codex"]
        assert viewmodel.state.prompt.text == ""
        assert viewmodel.state.prompt.cursor_position == 0
        assert viewmodel.state.autocompletion is None
        assert viewmodel.state.session_key == "run-codex"

    with patched_to_thread(run_command_use_case_module):
        asyncio.run(run())


def test_prompt_enter_submits_first_auth_param_completion() -> None:
    run_port = FakeRunPort(
        CommandAck(
            status=CommandAckStatus.ACCEPTED,
            run_id="run-codex",
            message="created",
        )
    )

    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=run_port,
            waiting_port=FakeWaitingPort(),
        )

        viewmodel.prompt_change(text="/auth ", cursor_position=6)

        await viewmodel.prompt_enter()

        assert run_port.called_with == ["auths/codex"]
        assert viewmodel.state.prompt.text == ""
        assert viewmodel.state.prompt.cursor_position == 0
        assert viewmodel.state.session_key == "run-codex"

    with patched_to_thread(run_command_use_case_module):
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


def test_console_screen_viewmodel_requests_exit_for_exit_command() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=FakeRunPort(
                CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"),
            ),
            waiting_port=FakeWaitingPort(),
        )

        await viewmodel.submit("/exit")

        assert viewmodel.state.transcript.items == []

    asyncio.run(run())


def test_console_screen_viewmodel_treats_bare_exit_as_text() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=FakeRunPort(
                CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"),
            ),
            waiting_port=FakeWaitingPort(),
        )

        await viewmodel.submit("exit")

        assert len(viewmodel.state.transcript.items) == 2
        assert isinstance(viewmodel.state.transcript.items[0], UserInputItem)
        assert viewmodel.state.transcript.items[0].text == "exit"
        assert isinstance(viewmodel.state.transcript.items[1], InfoItem)

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
        emitted_states: list[ConsoleScreenState] = []
        viewmodel.bind_on_state(emitted_states.append)

        await viewmodel.submit("/run chat")

        assert run_port.called_with == ["chat"]
        assert viewmodel.state.transcript.items == []
        assert viewmodel.state.view_status.kind == ViewStatusKind.RUNNING
        assert viewmodel.state.session_key == "run-1234"
        assert viewmodel.state.run_name == "chat"
        assert emitted_states[-1].run_name == "chat"
        assert viewmodel.state.prompt.text == ""
        assert viewmodel.state.prompt.cursor_position == 0

    with patched_to_thread(run_command_use_case_module):
        asyncio.run(run())


def test_console_screen_viewmodel_dispatches_auth_menu() -> None:
    run_port = FakeRunPort(
        CommandAck(
            status=CommandAckStatus.ACCEPTED,
            run_id="run-auth",
            message="created",
        )
    )

    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=run_port,
            waiting_port=FakeWaitingPort(),
        )

        await viewmodel.submit("/auth")

        assert run_port.called_with == ["auths/auth"]
        assert viewmodel.state.run_name == "auths/auth"
        assert viewmodel.state.session_key == "run-auth"

    with patched_to_thread(run_command_use_case_module):
        asyncio.run(run())


def test_console_screen_viewmodel_dispatches_auth_provider() -> None:
    run_port = FakeRunPort(
        CommandAck(
            status=CommandAckStatus.ACCEPTED,
            run_id="run-codex",
            message="created",
        )
    )

    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=run_port,
            waiting_port=FakeWaitingPort(),
        )

        await viewmodel.submit("/auth codex")

        assert run_port.called_with == ["auths/codex"]
        assert viewmodel.state.run_name == "auths/codex"
        assert viewmodel.state.session_key == "run-codex"

    with patched_to_thread(run_command_use_case_module):
        asyncio.run(run())


def test_console_screen_viewmodel_rejects_unknown_auth_provider() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused")),
            waiting_port=FakeWaitingPort(),
        )

        await viewmodel.submit("/auth unknown")

        assert viewmodel.state.view_status.kind == ViewStatusKind.ERROR
        assert viewmodel.state.view_status.message == (
            "Unknown auth provider. Use /auth, /auth codex, /auth minimax, or /auth bedrock."
        )
        assert isinstance(viewmodel.state.transcript.items[0], UserInputItem)
        assert viewmodel.state.transcript.items[0].text == "/auth unknown"
        assert isinstance(viewmodel.state.transcript.items[1], DispatchErrorItem)

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
        assert viewmodel.state.transcript.items == []
        assert [item.id for item in viewmodel.state.runs_table.rows] == ["run-1"]

    with patched_to_thread(list_runs_use_case_module):
        asyncio.run(run())


def test_console_screen_viewmodel_opens_models_table_for_models_command() -> None:
    async def run() -> None:
        models_port = FakeModelsPort()
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused")),
            waiting_port=FakeWaitingPort(),
            models_port=models_port,
        )
        viewmodel._run_event_context.run_id = "run-123"  # noqa: SLF001

        await viewmodel.submit("/models")

        assert models_port.called is True
        assert models_port.called_with == ["run-123"]
        assert viewmodel.state.models_table.visible is True
        assert viewmodel.state.runs_table.visible is False
        assert viewmodel.state.view_status.kind == ViewStatusKind.HIDDEN
        assert viewmodel.state.transcript.items == []
        assert [item.name for item in viewmodel.state.models_table.rows] == ["codex"]

    with patched_to_thread(list_models_use_case_module):
        asyncio.run(run())


def test_console_screen_viewmodel_selects_model_from_models_table() -> None:
    async def run() -> None:
        models_port = FakeModelsPort(
            models=[
                ModelsPortProviderItem(
                    name="codex",
                    source="global",
                    models=(ModelsPortModelItem(name="gpt-5.5", active=True),),
                ),
                ModelsPortProviderItem(
                    name="minimax",
                    source="global",
                    models=(
                        ModelsPortModelItem(name="MiniMax-M2.7"),
                        ModelsPortModelItem(name="MiniMax-M2.5"),
                    ),
                ),
            ]
        )
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused")),
            waiting_port=FakeWaitingPort(),
            models_port=models_port,
        )
        viewmodel._run_event_context.run_id = "run-123"  # noqa: SLF001

        await viewmodel.submit("/models")
        selected = await viewmodel.select_model(
            provider="minimax",
            model="MiniMax-M2.5",
        )

        providers = {provider.name: provider for provider in viewmodel.state.models_table.rows}
        minimax_models = {
            model.name: model for model in providers["minimax"].models
        }
        assert selected is True
        assert models_port.select_called_with == [
            ("run-123", "minimax", "MiniMax-M2.5"),
        ]
        assert minimax_models["MiniMax-M2.5"].active is True
        assert viewmodel.state.models_table.visible is True
        assert viewmodel.state.prompt.mode == PromptMode.MODELS_TABLE

    with patched_to_thread(list_models_use_case_module, select_model_use_case_module):
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


def test_console_screen_viewmodel_treats_chats_command_as_unknown() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused")),
            waiting_port=FakeWaitingPort(),
            runs_port=FakeRunsPort(),
        )

        await viewmodel.submit("/chats")

        assert viewmodel.state.runs_table.visible is False
        assert isinstance(viewmodel.state.transcript.items[0], UserInputItem)
        assert viewmodel.state.transcript.items[0].text == "/chats"
        assert isinstance(viewmodel.state.transcript.items[1], InfoItem)

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
        assert isinstance(viewmodel.state.transcript.items[0], DispatchErrorItem)

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
            strings=TuiStrings(unsupported_input_message="Use /run <skill>."),
        )

        await viewmodel.submit("hola")

        assert isinstance(viewmodel.state.transcript.items[0], UserInputItem)
        assert isinstance(viewmodel.state.transcript.items[1], InfoItem)
        assert viewmodel.state.transcript.items[1].text == "Use /run <skill>."
        assert viewmodel.state.view_status.kind == ViewStatusKind.HIDDEN
        assert viewmodel.state.prompt.text == ""
        assert viewmodel.state.prompt.cursor_position == 0

    asyncio.run(run())


def test_console_screen_viewmodel_on_start_preserves_initial_state() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=FakeRunPort(
                CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"),
            ),
            waiting_port=FakeWaitingPort(),
        )

        await viewmodel.on_start()

        assert viewmodel.state.session_key == "main"
        assert viewmodel.state.transcript.items == []

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
    assert isinstance(viewmodel.state.transcript.items[1], RunFinishedItem)
    assert viewmodel.state.transcript.items[0].step_id == "show_message"
    assert viewmodel.state.transcript.items[0].step_type == "notify"
    assert viewmodel.state.transcript.items[1].status == "succeeded"


def test_console_screen_viewmodel_runs_finished_action() -> None:
    async def run() -> None:
        run_port = FakeRunPort(
            CommandAck(
                status=CommandAckStatus.ACCEPTED,
                run_id="run-next",
                message="unused",
            )
        )
        events_port = FakeEventsPort()
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=run_port,
            events_port=events_port,
            waiting_port=FakeWaitingPort(),
        )

        attach_run_observer(viewmodel, events_port, "run-1234")
        with patched_to_thread(run_command_use_case_module):
            viewmodel.notify(
                [
                    _event(
                        LogEventType.RUN_FINISHED,
                        payload=RunFinishedPayload(
                            status="SUCCEEDED",
                            action=ActionRunValue(
                                uid="action-run-1",
                                type="run",
                                label="Run follow-up",
                                arg="ci",
                                params="--fast",
                            ),
                        ),
                    )
                ]
            )
            await asyncio.sleep(0)
            await asyncio.sleep(0)

        assert run_port.called_with == ["ci --fast"]
        assert events_port.subscribe_calls == ["run-1234", "run-next"]
        assert viewmodel.state.session_key == "run-next"
        assert viewmodel.state.run_name == "ci --fast"
        assert viewmodel.state.view_status.kind == ViewStatusKind.RUNNING
        assert viewmodel.state.transcript.items == []

    asyncio.run(run())


def test_console_screen_viewmodel_runs_notify_run_action() -> None:
    async def run() -> None:
        events: list[str] = []
        run_port = FakeRunPort(
            CommandAck(
                status=CommandAckStatus.ACCEPTED,
                run_id="run-child",
                message="unused",
            ),
            events=events,
        )
        events_port = FakeEventsPort()
        notify_action_port = FakeNotifyActionPort(events=events)
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=run_port,
            events_port=events_port,
            notify_action_port=notify_action_port,
            waiting_port=FakeWaitingPort(),
        )

        attach_run_observer(viewmodel, events_port, "run-parent")
        with patched_to_thread(run_command_use_case_module):
            viewmodel.notify(
                [
                    _event(
                        LogEventType.STEP_SUCCESS,
                        step_id="run_child",
                        step_type="notify",
                        payload=StepSuccessPayload(
                            output=OutputPayload(
                                text="Run child",
                                value=NotifyActionValue(
                                    message="Run child",
                                    action=ActionRunValue(
                                        uid="action-run-1",
                                        type="run",
                                        label="Run child",
                                        arg="--file child.yaml",
                                        params="--arg message=hello",
                                    ),
                                ),
                                body_ref=None,
                            )
                        ),
                    ),
                    _event(
                        LogEventType.RUN_FINISHED,
                        payload=RunFinishedPayload(status="SUCCEEDED"),
                        event_id="evt-2",
                        sequence=2,
                    ),
                ]
            )
            await asyncio.sleep(0)
            await asyncio.sleep(0)

        assert events == ["run", "done"]
        assert notify_action_port.done_calls == [("run-1234", "action-run-1")]
        assert run_port.called_with == ["--file child.yaml --arg message=hello"]
        assert events_port.subscribe_calls == ["run-parent", "run-child"]
        assert viewmodel.state.session_key == "run-child"
        assert viewmodel.state.run_name == "--file child.yaml --arg message=hello"

    asyncio.run(run())


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
            run_name="run-1234",
            status=RunStatus.RUNNING,
        )
        viewmodel.notify(
            [
                _event(
                    LogEventType.RUN_WAITING,
                    step_type="wait_input",
                    payload=RunWaitingPayload(
                        output=_waiting_output("Write a message. Type exit, quit, or bye to stop.")
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


def test_console_screen_viewmodel_sends_unknown_slash_text_when_waiting_for_input() -> None:
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
            run_name="run-1234",
            status=RunStatus.RUNNING,
        )
        viewmodel.notify(
            [
                _event(
                    LogEventType.RUN_WAITING,
                    step_type="wait_input",
                    payload=RunWaitingPayload(output=_waiting_output("Write a message.")),
                )
            ]
        )

        await viewmodel.submit("/home/fede/project/file.py\nnext line")

        assert waiting_port.called_with == [("run-1234", "/home/fede/project/file.py\nnext line")]
        assert isinstance(viewmodel.state.transcript.items[-1], RunResumeItem)
        assert viewmodel.state.view_status.kind == ViewStatusKind.RUNNING

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
                payload=RunWaitingPayload(output=_waiting_webhook_output()),
            )
        ]
    )
    previous_items = list(viewmodel.state.transcript.items)

    async def run() -> None:
        await viewmodel.submit("hola")

    asyncio.run(run())

    assert viewmodel.state.transcript.items == previous_items
    assert viewmodel.state.view_status.kind == ViewStatusKind.WAITING
    assert viewmodel.state.prompt.text == ""
    assert viewmodel.state.prompt.cursor_position == 0


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
            run_name="run-1234",
            status=RunStatus.RUNNING,
        )
        viewmodel.notify(
            [
                _event(
                    LogEventType.RUN_WAITING,
                    step_type="wait_input",
                    payload=RunWaitingPayload(output=_waiting_output()),
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
            run_name="run-1234",
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
                    payload=RunWaitingPayload(output=_waiting_output("Write a short summary")),
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
            item
            for item in viewmodel.state.transcript.items
            if isinstance(item, (RunOutputItem, StepOutputItem))
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


def test_console_screen_viewmodel_uses_run_name_on_resume_after_wait_input() -> None:
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
                    payload=RunWaitingPayload(output=_waiting_output()),
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
