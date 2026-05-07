from __future__ import annotations

import asyncio

import pytest

import skiller.interfaces.tui.usecase.list_runs_use_case as list_runs_use_case_module
import skiller.interfaces.tui.usecase.run_command_use_case as run_command_use_case_module
from skiller.interfaces.tui.port.run_port import (
    CommandAck,
    CommandAckStatus,
    ObserverType,
    PollingEvent,
    PollingEventKind,
)
from skiller.interfaces.tui.port.runs_port import RunsPortItem
from skiller.interfaces.tui.usecase import (
    submit_waiting_input_use_case as submit_waiting_input_use_case_module,
)
from skiller.interfaces.tui.viewmodel.console_screen_state import (
    AgentAssistantMessageItem,
    AgentToolCallItem,
    AgentToolResultItem,
    CompletionItem,
    CompletionState,
    ConsoleScreenState,
    DispatchErrorItem,
    InfoItem,
    OutputFormat,
    RunAckItem,
    RunOutputItem,
    RunResumeItem,
    RunStatusItem,
    RunStepItem,
    ScreenStatus,
    UserInputItem,
)
from skiller.interfaces.tui.viewmodel.console_screen_viewmodel import ConsoleScreenViewModel
from tests.unit.interfaces.tui.support import (
    FakeRunsPort,
    build_viewmodel,
    make_runs_port_item,
    patched_to_thread,
)

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


class FakeRunPort:
    def __init__(self, ack: CommandAck) -> None:
        self.ack = ack
        self.called_with: list[str] = []
        self.subscribed: list[object] = []
        self.unsubscribed: list[object] = []

    def run(self, raw_args: str) -> CommandAck:
        self.called_with.append(raw_args)
        return self.ack

    def subscribe(self, observer: object) -> None:
        self.subscribed.append(observer)

    def unsubscribe(self, observer: object) -> None:
        self.unsubscribed.append(observer)


class FakeWaitingPort:
    def __init__(self, ack: CommandAck | None = None) -> None:
        self.ack = ack or CommandAck(status=CommandAckStatus.ACCEPTED)
        self.called_with: list[tuple[str, str]] = []

    def send_input(self, *, run_id: str, text: str) -> CommandAck:
        self.called_with.append((run_id, text))
        return self.ack


def attach_run_observer(
    viewmodel: ConsoleScreenViewModel,
    run_port: FakeRunPort,
    run_id: str,
) -> None:
    viewmodel.run_id = run_id
    run_port.subscribe(viewmodel)


def test_console_screen_state_defaults_to_idle_main_session() -> None:
    state = ConsoleScreenState()

    assert state.session_key == "main"
    assert state.screen_status == ScreenStatus.READY
    assert state.runs_table_visible is False
    assert state.runs_table_command == ""
    assert state.runs == ()
    assert state.waiting_prompt == ""
    assert state.prompt_text == ""
    assert state.prompt_cursor_position == 0
    assert state.transcript_items == []
    assert state.autocompletion is None


def test_completion_state_exposes_selected_item() -> None:
    state = CompletionState(
        visible=True,
        query="/ru",
        items=(
            CompletionItem(label="runs"),
            CompletionItem(label="run"),
            CompletionItem(label="resume"),
        ),
        selected_index=1,
        replace_from=0,
        replace_to=3,
    )

    assert state.selected_item is not None
    assert state.selected_item.label == "run"


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

        assert viewmodel.state.prompt_text == "/runs "
        assert viewmodel.state.prompt_cursor_position == 6
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

        assert viewmodel.state.prompt_text == ""
        assert viewmodel.state.prompt_cursor_position == 0
        assert viewmodel.state.session_key == "run-1234"
        assert viewmodel.run_id == "run-1234"

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

        assert viewmodel.state.transcript_items == []

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
        assert isinstance(viewmodel.state.transcript_items[0], UserInputItem)
        assert isinstance(viewmodel.state.transcript_items[1], RunAckItem)
        assert viewmodel.state.transcript_items[0].text == "/run chat"
        assert viewmodel.state.transcript_items[1].skill == "chat"
        assert viewmodel.state.transcript_items[1].run_id == "run-1234"
        assert viewmodel.state.screen_status == ScreenStatus.RUNNING
        assert viewmodel.state.session_key == "run-1234"
        assert viewmodel.state.prompt_text == ""
        assert viewmodel.state.prompt_cursor_position == 0

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

        assert viewmodel.state.runs_table_visible is True
        assert viewmodel.state.screen_status == ScreenStatus.READY
        assert isinstance(viewmodel.state.transcript_items[0], UserInputItem)
        assert viewmodel.state.transcript_items[0].text == "/runs"
        assert [item.id for item in viewmodel.state.runs] == ["run-1"]

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
        assert viewmodel.state.runs_table_visible is True
        assert viewmodel.state.screen_status == ScreenStatus.READY
        assert [item.id for item in viewmodel.state.runs] == ["run-1"]

    with patched_to_thread(list_runs_use_case_module):
        asyncio.run(run())


def test_console_screen_viewmodel_opens_agents_table_for_waiting_input_runs() -> None:
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

        await viewmodel.submit("/agents")

        assert runs_port.called_with == [(20, ["WAITING"])]
        assert viewmodel.state.runs_table_visible is True
        assert viewmodel.state.runs_table_command == "/agents"
        assert [item.id for item in viewmodel.state.runs] == ["run-input"]

    with patched_to_thread(list_runs_use_case_module):
        asyncio.run(run())


def test_console_screen_viewmodel_selects_agents_waiting_row_and_reconnects_run() -> None:
    run_port = FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"))
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=run_port,
        waiting_port=FakeWaitingPort(),
        runs_port=FakeRunsPort(),
    )
    viewmodel.state.runs_table_visible = True
    viewmodel.state.runs_table_command = "/agents"
    viewmodel.run_id = "run-old"

    viewmodel.select_runs_table_row(
        prompt_text="",
        status="waiting-i",
        run_id="run-1234",
        skill_name="wait_input_test",
        is_exit=False,
    )

    assert viewmodel.state.runs_table_visible is False
    assert viewmodel.state.runs_table_command == ""
    assert viewmodel.run_id == "run-1234"
    assert viewmodel.state.session_key == "run-1234"
    assert viewmodel.state.screen_status == ScreenStatus.RUNNING
    assert run_port.unsubscribed == [viewmodel]
    assert run_port.subscribed[-1] is viewmodel


def test_console_screen_viewmodel_selects_runs_row_and_only_closes_table() -> None:
    run_port = FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"))
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=run_port,
        waiting_port=FakeWaitingPort(),
        runs_port=FakeRunsPort(),
    )
    viewmodel.state.runs_table_visible = True
    viewmodel.state.runs_table_command = "/runs"
    viewmodel.run_id = "run-old"

    viewmodel.select_runs_table_row(
        prompt_text="",
        status="waiting-i",
        run_id="run-1234",
        skill_name="wait_input_test",
        is_exit=False,
    )

    assert viewmodel.state.runs_table_visible is False
    assert viewmodel.state.runs_table_command == ""
    assert viewmodel.run_id == "run-old"
    assert run_port.unsubscribed == []
    assert run_port.subscribed == []


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

        assert viewmodel.state.runs_table_visible is False
        assert viewmodel.state.screen_status == ScreenStatus.ERROR
        assert isinstance(viewmodel.state.transcript_items[0], UserInputItem)
        assert isinstance(viewmodel.state.transcript_items[1], DispatchErrorItem)

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

        assert isinstance(viewmodel.state.transcript_items[0], UserInputItem)
        assert isinstance(viewmodel.state.transcript_items[1], InfoItem)
        assert (
            viewmodel.state.transcript_items[1].text
            == "Use /run <skill> to execute a skill."
        )
        assert viewmodel.state.screen_status == ScreenStatus.READY
        assert viewmodel.state.prompt_text == ""
        assert viewmodel.state.prompt_cursor_position == 0

    asyncio.run(run())


def test_console_screen_viewmodel_maps_dispatch_error() -> None:
    run_port = FakeRunPort(
        CommandAck(
            status=CommandAckStatus.ERROR,
            message="error: skill not found",
        )
    )

    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=run_port,
            waiting_port=FakeWaitingPort(),
        )

        await viewmodel.submit("/run missing_skill")

        assert isinstance(viewmodel.state.transcript_items[1], DispatchErrorItem)
        assert viewmodel.state.transcript_items[1].message == "error: skill not found"
        assert viewmodel.state.screen_status == ScreenStatus.ERROR
        assert viewmodel.state.session_key == "main"

    with patched_to_thread(run_command_use_case_module):
        asyncio.run(run())


def test_console_screen_viewmodel_subscribes_and_applies_polling_events() -> None:
    run_port = FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"))
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=run_port,
        waiting_port=FakeWaitingPort(),
    )

    attach_run_observer(viewmodel, run_port, "run-1234")
    viewmodel.notify([
        PollingEvent(
            kind=PollingEventKind.LOG,
            run_id="run-1234",
            event_type="STEP_STARTED",
            step="show_message",
            step_type="notify",
            event_id="evt-1",
        ),
        PollingEvent(
            kind=PollingEventKind.STATUS,
            run_id="run-1234",
            status="RUNNING",
            text="[1234] RUNNING",
        ),
        PollingEvent(
            kind=PollingEventKind.STATUS,
            run_id="run-1234",
            status="SUCCEEDED",
            text="[1234] SUCCEEDED",
        ),
    ])

    assert viewmodel.type == ObserverType.RUN
    assert viewmodel.run_id == "run-1234"
    assert run_port.subscribed == [viewmodel]
    assert viewmodel.state.screen_status == ScreenStatus.READY
    assert isinstance(viewmodel.state.transcript_items[0], RunStepItem)
    assert isinstance(viewmodel.state.transcript_items[1], RunStatusItem)
    assert viewmodel.state.transcript_items[0].step_id == "show_message"
    assert viewmodel.state.transcript_items[0].step_type == "notify"
    assert viewmodel.state.transcript_items[1].status == "succeeded"


def test_console_screen_viewmodel_sends_plain_text_when_waiting_for_input() -> None:
    run_port = FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"))
    waiting_port = FakeWaitingPort(
        CommandAck(status=CommandAckStatus.ACCEPTED, run_id="run-1234")
    )

    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=run_port,
            waiting_port=waiting_port,
        )
        attach_run_observer(viewmodel, run_port, "run-1234")
        viewmodel.notify(
            [
                PollingEvent(
                    kind=PollingEventKind.LOG,
                    run_id="run-1234",
                    event_type="RUN_WAITING",
                    step_type="wait_input",
                    output="Write a message. Type exit, quit, or bye to stop.",
                ),
                PollingEvent(
                    kind=PollingEventKind.STATUS,
                    run_id="run-1234",
                    status="WAITING",
                )
            ]
        )

        await viewmodel.submit("hello world")

        assert waiting_port.called_with == [("run-1234", "hello world")]
        assert isinstance(viewmodel.state.transcript_items[-2], UserInputItem)
        assert viewmodel.state.transcript_items[-2].text == "hello world"
        assert isinstance(viewmodel.state.transcript_items[-1], RunResumeItem)
        assert viewmodel.state.transcript_items[-1].run_id == "run-1234"
        assert viewmodel.state.transcript_items[-1].skill == "run-1234"
        assert viewmodel.state.screen_status == ScreenStatus.RUNNING
        assert viewmodel.state.waiting_prompt == ""
        assert viewmodel.state.prompt_text == ""
        assert viewmodel.state.prompt_cursor_position == 0

    with patched_to_thread(submit_waiting_input_use_case_module):
        asyncio.run(run())


def test_console_screen_viewmodel_does_not_send_plain_text_when_waiting_not_input() -> None:
    run_port = FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"))
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=run_port,
        waiting_port=FakeWaitingPort(),
    )
    attach_run_observer(viewmodel, run_port, "run-1234")
    viewmodel.notify(
        [
            PollingEvent(
                kind=PollingEventKind.LOG,
                run_id="run-1234",
                event_type="RUN_WAITING",
                step_type="wait_webhook",
            ),
            PollingEvent(
                kind=PollingEventKind.STATUS,
                run_id="run-1234",
                status="WAITING",
            )
        ]
    )

    async def run() -> None:
        await viewmodel.submit("hola")

    asyncio.run(run())

    assert isinstance(viewmodel.state.transcript_items[-1], InfoItem)


def test_console_screen_viewmodel_maps_waiting_input_rejection() -> None:
    run_port = FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"))
    waiting_port = FakeWaitingPort(
        CommandAck(status=CommandAckStatus.REJECTED, message="error: input rejected")
    )

    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=run_port,
            waiting_port=waiting_port,
        )
        attach_run_observer(viewmodel, run_port, "run-1234")
        viewmodel.notify(
            [
                PollingEvent(
                    kind=PollingEventKind.LOG,
                    run_id="run-1234",
                    event_type="RUN_WAITING",
                    step_type="wait_input",
                ),
                PollingEvent(
                    kind=PollingEventKind.STATUS,
                    run_id="run-1234",
                    status="WAITING",
                )
            ]
        )

        await viewmodel.submit("hello")

        assert waiting_port.called_with == [("run-1234", "hello")]
        assert isinstance(viewmodel.state.transcript_items[-1], DispatchErrorItem)
        assert viewmodel.state.screen_status == ScreenStatus.ERROR
        assert viewmodel.state.prompt_text == ""
        assert viewmodel.state.prompt_cursor_position == 0

    with patched_to_thread(submit_waiting_input_use_case_module):
        asyncio.run(run())


def test_console_screen_viewmodel_infers_waiting_input_without_run_waiting_step_type() -> None:
    run_port = FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"))
    waiting_port = FakeWaitingPort(
        CommandAck(status=CommandAckStatus.ACCEPTED, run_id="run-1234")
    )

    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=run_port,
            waiting_port=waiting_port,
        )
        attach_run_observer(viewmodel, run_port, "run-1234")
        viewmodel.notify(
            [
                PollingEvent(
                    kind=PollingEventKind.LOG,
                    run_id="run-1234",
                    event_type="STEP_STARTED",
                    step="ask_user",
                    step_type="wait_input",
                ),
                PollingEvent(
                    kind=PollingEventKind.LOG,
                    run_id="run-1234",
                    event_type="RUN_WAITING",
                    step="ask_user",
                    step_type="",
                    output="Write a short summary",
                ),
                PollingEvent(
                    kind=PollingEventKind.STATUS,
                    run_id="run-1234",
                    status="WAITING",
                ),
            ]
        )
        assert viewmodel.state.waiting_prompt == "Write a short summary"

        await viewmodel.submit("hola mundo")

        assert waiting_port.called_with == [("run-1234", "hola mundo")]
        outputs = [
            item for item in viewmodel.state.transcript_items if isinstance(item, RunOutputItem)
        ]
        assert outputs == []
        assert viewmodel.state.waiting_prompt == ""
        assert viewmodel.state.prompt_text == ""
        assert viewmodel.state.prompt_cursor_position == 0

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
        CommandAck(status=CommandAckStatus.ACCEPTED, run_id="run-1234")
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
                PollingEvent(
                    kind=PollingEventKind.LOG,
                    run_id="run-1234",
                    event_type="RUN_WAITING",
                    step_type="wait_input",
                ),
                PollingEvent(
                    kind=PollingEventKind.STATUS,
                    run_id="run-1234",
                    status="WAITING",
                ),
            ]
        )

        await viewmodel.submit("hola mundo")

        last_item = viewmodel.state.transcript_items[-1]
        assert isinstance(last_item, RunResumeItem)
        assert last_item.run_id == "run-1234"
        assert last_item.skill == "wait_input_test"
        assert viewmodel.state.prompt_text == ""
        assert viewmodel.state.prompt_cursor_position == 0

    with patched_to_thread(
        run_command_use_case_module,
        submit_waiting_input_use_case_module,
    ):
        asyncio.run(run())


def test_console_screen_viewmodel_ignores_technical_resume_events() -> None:
    run_port = FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"))
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=run_port,
        waiting_port=FakeWaitingPort(),
    )

    viewmodel.notify(
        [
            PollingEvent(
                kind=PollingEventKind.LOG,
                run_id="run-1234",
                event_type="INPUT_RECEIVED",
                text='[1234] INPUT_RECEIVED step="ask_user"',
                event_id="evt-1",
            ),
            PollingEvent(
                kind=PollingEventKind.LOG,
                run_id="run-1234",
                event_type="RUN_RESUME",
                text='[1234] RUN_RESUME source="manual"',
                event_id="evt-2",
            ),
        ]
    )

    assert viewmodel.state.transcript_items == []


def test_console_screen_viewmodel_dedupes_replayed_waiting_event_by_event_id() -> None:
    run_port = FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"))
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=run_port,
        waiting_port=FakeWaitingPort(),
    )

    first_batch = [
        PollingEvent(
            kind=PollingEventKind.LOG,
            run_id="run-1234",
            event_type="RUN_WAITING",
            step="ask_user",
            step_type="wait_input",
            output="Write a short summary",
            event_id="evt-wait-1",
        )
    ]
    replay_batch = [
        PollingEvent(
            kind=PollingEventKind.LOG,
            run_id="run-1234",
            event_type="RUN_WAITING",
            step="ask_user",
            step_type="wait_input",
            output="Write a short summary",
            event_id="evt-wait-1",
        )
    ]

    viewmodel.notify(first_batch)
    viewmodel.notify(replay_batch)

    outputs = [
        item for item in viewmodel.state.transcript_items if isinstance(item, RunOutputItem)
    ]
    assert outputs == []
    assert viewmodel.state.waiting_prompt == "Write a short summary"


def test_console_screen_viewmodel_skips_input_received_wait_output_block() -> None:
    run_port = FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"))
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=run_port,
        waiting_port=FakeWaitingPort(),
    )

    viewmodel.notify(
        [
            PollingEvent(
                kind=PollingEventKind.LOG,
                run_id="run-1234",
                event_type="RUN_WAITING",
                step="ask_user",
                step_type="wait_input",
                output=_INPUT_RECEIVED_OUTPUT,
                event_id="evt-wait-input-received",
            )
        ]
    )

    outputs = [
        item for item in viewmodel.state.transcript_items if isinstance(item, RunOutputItem)
    ]
    assert outputs == []


def test_console_screen_viewmodel_dedupes_wait_input_step_by_step_id() -> None:
    run_port = FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"))
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=run_port,
        waiting_port=FakeWaitingPort(),
    )

    viewmodel.notify(
        [
            PollingEvent(
                kind=PollingEventKind.LOG,
                run_id="run-1234",
                event_type="STEP_STARTED",
                step="ask_user",
                step_type="wait_input",
                event_id="evt-step-1",
            ),
            PollingEvent(
                kind=PollingEventKind.LOG,
                run_id="run-1234",
                event_type="STEP_STARTED",
                step="ask_user",
                step_type="wait_input",
                event_id="evt-step-2",
            ),
        ]
    )

    steps = [item for item in viewmodel.state.transcript_items if isinstance(item, RunStepItem)]
    assert len(steps) == 1


def test_console_screen_viewmodel_skips_step_success_wait_input_input_received_output() -> None:
    run_port = FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"))
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=run_port,
        waiting_port=FakeWaitingPort(),
    )

    viewmodel.notify(
        [
            PollingEvent(
                kind=PollingEventKind.LOG,
                run_id="run-1234",
                event_type="STEP_SUCCESS",
                step="ask_user",
                step_type="wait_input",
                output=_INPUT_RECEIVED_OUTPUT_TRUNCATED,
                event_id="evt-step-success-input-received",
            )
        ]
    )

    outputs = [
        item for item in viewmodel.state.transcript_items if isinstance(item, RunOutputItem)
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
            PollingEvent(
                kind=PollingEventKind.LOG,
                run_id="run-1234",
                event_type="STEP_SUCCESS",
                step="support_agent",
                step_type="agent",
                output='{"text":"hola"}',
                event_id="evt-agent-out",
            ),
            PollingEvent(
                kind=PollingEventKind.LOG,
                run_id="run-1234",
                event_type="STEP_SUCCESS",
                step="run_check",
                step_type="shell",
                output='{"value":{"ok":true}}',
                event_id="evt-shell-out",
            ),
        ]
    )

    outputs = [
        item for item in viewmodel.state.transcript_items if isinstance(item, RunOutputItem)
    ]
    assert len(outputs) == 2
    assert outputs[0].format == OutputFormat.MARKDOWN
    assert outputs[1].format == OutputFormat.STRUCTURED


def test_console_screen_viewmodel_appends_agent_tool_call_and_result_items() -> None:
    run_port = FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"))
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=run_port,
        waiting_port=FakeWaitingPort(),
    )

    viewmodel.notify(
        [
            PollingEvent(
                kind=PollingEventKind.LOG,
                run_id="run-1234",
                event_type="AGENT_TOOL_CALL",
                step="support_agent",
                step_type="agent",
                tool="shell",
                command="git status --short",
                event_id="evt-agent-tool-call",
            ),
            PollingEvent(
                kind=PollingEventKind.LOG,
                run_id="run-1234",
                event_type="AGENT_TOOL_RESULT",
                step="support_agent",
                step_type="agent",
                tool="shell",
                output='{"text":"M docs/configuration.md","value":{"ok":true}}',
                event_id="evt-agent-tool-result",
            ),
        ]
    )

    assert isinstance(viewmodel.state.transcript_items[0], AgentToolCallItem)
    assert viewmodel.state.transcript_items[0].command == "git status --short"
    assert isinstance(viewmodel.state.transcript_items[1], AgentToolResultItem)
    assert viewmodel.state.transcript_items[1].preview == "M docs/configuration.md"


def test_console_screen_viewmodel_appends_agent_assistant_message_item() -> None:
    run_port = FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"))
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=run_port,
        waiting_port=FakeWaitingPort(),
    )

    viewmodel.notify(
        [
            PollingEvent(
                kind=PollingEventKind.LOG,
                run_id="run-1234",
                event_type="AGENT_ASSISTANT_MESSAGE",
                step="support_agent",
                step_type="agent",
                message_type="tool_calls",
                assistant_text="I will inspect the repository state.",
                event_id="evt-agent-assistant",
            ),
        ]
    )

    assert isinstance(viewmodel.state.transcript_items[0], AgentAssistantMessageItem)
    assert viewmodel.state.transcript_items[0].message_type == "tool_calls"
    assert viewmodel.state.transcript_items[0].text == "I will inspect the repository state."


def test_console_screen_viewmodel_dedupes_agent_final_message_against_step_success() -> None:
    run_port = FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"))
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=run_port,
        waiting_port=FakeWaitingPort(),
    )

    viewmodel.notify(
        [
            PollingEvent(
                kind=PollingEventKind.LOG,
                run_id="run-1234",
                event_type="AGENT_ASSISTANT_MESSAGE",
                step="support_agent",
                step_type="agent",
                message_type="final",
                assistant_text="Hecho.",
                event_id="evt-agent-final",
            ),
            PollingEvent(
                kind=PollingEventKind.LOG,
                run_id="run-1234",
                event_type="STEP_SUCCESS",
                step="support_agent",
                step_type="agent",
                output='{"text":"Hecho."}',
                event_id="evt-agent-step-success",
            ),
        ]
    )

    assert len(viewmodel.state.transcript_items) == 1
    assert isinstance(viewmodel.state.transcript_items[0], AgentAssistantMessageItem)
    assert viewmodel.state.transcript_items[0].message_type == "final"


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
            PollingEvent(
                kind=PollingEventKind.LOG,
                run_id="run-1234",
                event_type="RUN_WAITING",
                step="ask_user",
                step_type="wait_input",
                output=_WAITING_PROMPT_OUTPUT,
                event_id="evt-wait-2",
            )
        ]
    )

    outputs = [
        item for item in viewmodel.state.transcript_items if isinstance(item, RunOutputItem)
    ]
    assert outputs == []
    assert viewmodel.state.waiting_prompt == "Write a message. Type exit, quit, or bye to stop."


def test_console_screen_viewmodel_sets_wait_prompt_from_status_fallback() -> None:
    run_port = FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"))
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=run_port,
        waiting_port=FakeWaitingPort(),
    )

    viewmodel.notify(
        [
            PollingEvent(
                kind=PollingEventKind.STATUS,
                run_id="run-1234",
                status="WAITING",
                prompt="Write a message. Type exit, quit, or bye to stop.",
            )
        ]
    )

    assert viewmodel.state.screen_status == ScreenStatus.WAITING
    assert viewmodel.state.waiting_prompt == "Write a message. Type exit, quit, or bye to stop."
