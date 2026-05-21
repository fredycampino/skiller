from __future__ import annotations

import asyncio

import pytest

from stui.port.event_models import LogEvent
from stui.port.waiting_port import WaitingInputAck, WaitingInputStatus
from stui.usecase import (
    submit_waiting_input_use_case as submit_waiting_input_use_case_module,
)
from stui.usecase.run_event_context import (
    RunEventContext,
    RunMode,
    RunStatus,
)
from stui.usecase.submit_waiting_input_use_case import (
    SubmitWaitingInputUseCase,
)
from stui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    DispatchErrorItem,
    PromptState,
    RunAckItem,
    RunResumeItem,
    ViewStatusKind,
)

pytestmark = pytest.mark.unit


class FakeWaitingPort:
    def __init__(self, ack: WaitingInputAck) -> None:
        self.ack = ack
        self.called_with: list[tuple[str, str]] = []

    def send_input(self, *, run_id: str, text: str) -> WaitingInputAck:
        self.called_with.append((run_id, text))
        return self.ack


class FakeRunPort:
    def __init__(self) -> None:
        self.status_called_with: list[str] = []

    def status(self, run_id: str):  # noqa: ANN001
        self.status_called_with.append(run_id)
        raise AssertionError(f"unexpected status call: {run_id}")


class FakeEventsPort:
    def __init__(self, *, current_run_id: str = "", current_listener: object | None = None) -> None:
        self.subscribed: list[object] = []
        self.unsubscribed: list[object] = []
        self.current_run_id = current_run_id
        self.current_listener = current_listener

    def subscribe(self, *, run_id: str, listener: FakeObserver) -> None:
        if self.current_listener is not None:
            previous_listener = self.current_listener
            self.unsubscribe()
            self.unsubscribed.append(previous_listener)
        self.current_listener = listener
        self.current_run_id = run_id
        assert self.current_run_id == "run-5678"
        self.subscribed.append(listener)

    def unsubscribe(self) -> None:
        self.current_listener = None
        self.current_run_id = ""


class FakeObserver:
    def notify(self, events: list[LogEvent]) -> None:
        _ = events

    def get_max_page(self) -> int:
        return 100


def _run_context(
    *,
    run_id: str = "",
    skill_name: str = "",
    mode: RunMode = RunMode.CHAT,
    status: RunStatus = RunStatus.RUNNING,
) -> RunEventContext:
    return RunEventContext(
        run_id=run_id,
        skill_name=skill_name,
        mode=mode,
        status=status,
    )


def test_submit_waiting_input_use_case_accepts_and_resumes(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_to_thread(function, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return function(*args, **kwargs)

    monkeypatch.setattr(
        submit_waiting_input_use_case_module.asyncio,
        "to_thread",
        fake_to_thread,
    )

    async def run() -> None:
        waiting_port = FakeWaitingPort(
            WaitingInputAck(
                status=WaitingInputStatus.ACCEPTED,
                run_id="run-5678",
                message="",
            )
        )
        run_port = FakeRunPort()
        events_port = FakeEventsPort()
        context = _run_context()
        context.activate_run(
            "run-1234",
            skill_name="wait_input_test",
            status=RunStatus.WAITING_INPUT,
        )
        use_case = SubmitWaitingInputUseCase(
            waiting_port=waiting_port,
            run_port=run_port,
            events_port=events_port,
            context=context,
        )
        observer = FakeObserver()
        events_port.current_run_id = "run-1234"
        events_port.current_listener = observer
        state = ConsoleScreenState(
            session_key="main",
            prompt=PromptState(waiting_prompt="Write a message"),
        )
        state.transcript.items.append(RunAckItem(skill="wait_input_test", run_id="run-1234"))

        result = await use_case.execute(
            observer,
            state=state,
            text="hello world",
        )

        assert waiting_port.called_with == [("run-1234", "hello world")]
        assert run_port.status_called_with == []
        assert events_port.unsubscribed == [observer]
        assert events_port.subscribed == [observer]
        assert events_port.current_run_id == "run-5678"
        assert result.state is state
        assert state.session_key == "run-5678"
        assert state.view_status.kind == ViewStatusKind.RUNNING
        assert context.run_id == "run-5678"
        assert context.skill_name == "wait_input_test"
        assert context.mode == RunMode.CHAT
        assert context.status == RunStatus.RUNNING
        assert state.prompt.waiting_prompt == ""
        assert state.prompt.text == ""
        assert state.prompt.cursor_position == 0
        assert isinstance(state.transcript.items[-1], RunResumeItem)
        assert state.transcript.items[-1].skill == "wait_input_test"
        assert state.transcript.items[-1].run_id == "run-1234"

    asyncio.run(run())


def test_submit_waiting_input_use_case_rejects_input(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_to_thread(function, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return function(*args, **kwargs)

    monkeypatch.setattr(
        submit_waiting_input_use_case_module.asyncio,
        "to_thread",
        fake_to_thread,
    )

    async def run() -> None:
        waiting_port = FakeWaitingPort(
            WaitingInputAck(
                status=WaitingInputStatus.REJECTED,
                run_id="run-1234",
                message="error: input rejected",
            )
        )
        run_port = FakeRunPort()
        events_port = FakeEventsPort()
        use_case = SubmitWaitingInputUseCase(
            waiting_port=waiting_port,
            run_port=run_port,
            events_port=events_port,
            context=_run_context(
                run_id="run-1234",
                skill_name="wait_input_test",
                status=RunStatus.WAITING_INPUT,
            ),
        )
        observer = FakeObserver()
        events_port.current_run_id = "run-1234"
        events_port.current_listener = observer
        state = ConsoleScreenState(
            session_key="main",
            prompt=PromptState(waiting_prompt="Write a message"),
        )

        result = await use_case.execute(
            observer,
            state=state,
            text="hello",
        )

        assert waiting_port.called_with == [("run-1234", "hello")]
        assert run_port.status_called_with == []
        assert events_port.subscribed == []
        assert events_port.unsubscribed == []
        assert events_port.current_run_id == "run-1234"
        assert result.state is state
        assert state.view_status.kind == ViewStatusKind.ERROR
        assert isinstance(state.transcript.items[-1], DispatchErrorItem)
        assert state.transcript.items[-1].message == "error: input rejected"

    asyncio.run(run())


def test_submit_waiting_input_use_case_normalizes_user_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_to_thread(function, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return function(*args, **kwargs)

    monkeypatch.setattr(
        submit_waiting_input_use_case_module.asyncio,
        "to_thread",
        fake_to_thread,
    )

    async def run() -> None:
        waiting_port = FakeWaitingPort(
            WaitingInputAck(
                status=WaitingInputStatus.ACCEPTED,
                run_id="run-5678",
                message="",
            )
        )
        use_case = SubmitWaitingInputUseCase(
            waiting_port=waiting_port,
            run_port=FakeRunPort(),
            events_port=FakeEventsPort(),
            context=_run_context(
                run_id="run-1234",
                skill_name="wait_input_test",
                status=RunStatus.WAITING_INPUT,
            ),
        )

        await use_case.execute(
            FakeObserver(),
            state=ConsoleScreenState(session_key="main"),
            text="  hello world  ",
        )

        assert waiting_port.called_with == [("run-1234", "hello world")]

    asyncio.run(run())


def test_submit_waiting_input_use_case_ignores_missing_waiting_run() -> None:
    waiting_port = FakeWaitingPort(
        WaitingInputAck(
            status=WaitingInputStatus.ACCEPTED,
            run_id="run-5678",
            message="",
        )
    )
    run_port = FakeRunPort()
    events_port = FakeEventsPort()
    use_case = SubmitWaitingInputUseCase(
        waiting_port=waiting_port,
        run_port=run_port,
        events_port=events_port,
        context=_run_context(),
    )
    observer = FakeObserver()
    state = ConsoleScreenState(session_key="main")

    async def run() -> None:
        result = await use_case.execute(
            observer,
            state=state,
            text="hello",
        )

        assert result.state is state
        assert waiting_port.called_with == []
        assert events_port.subscribed == []
        assert events_port.unsubscribed == []
        assert state.transcript.items == []
        assert state.view_status.kind == ViewStatusKind.HIDDEN

    asyncio.run(run())
