from __future__ import annotations

import asyncio

import pytest

from skiller.interfaces.tui.port.run_port import CommandAck, CommandAckStatus
from skiller.interfaces.tui.usecase import (
    submit_waiting_input_use_case as submit_waiting_input_use_case_module,
)
from skiller.interfaces.tui.usecase.run_event_context import (
    RunEventContext,
    RunStatus,
)
from skiller.interfaces.tui.usecase.submit_waiting_input_use_case import (
    SubmitWaitingInputUseCase,
)
from skiller.interfaces.tui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    DispatchErrorItem,
    PromptState,
    RunAckItem,
    RunResumeItem,
    UserInputItem,
    ViewStatusKind,
)

pytestmark = pytest.mark.unit


class FakeWaitingPort:
    def __init__(self, ack: CommandAck) -> None:
        self.ack = ack
        self.called_with: list[tuple[str, str]] = []

    def send_input(self, *, run_id: str, text: str) -> CommandAck:
        self.called_with.append((run_id, text))
        return self.ack


class FakeRunPort:
    def __init__(self) -> None:
        self.subscribed: list[object] = []
        self.unsubscribed: list[object] = []

    def subscribe(self, observer: object) -> None:
        assert getattr(observer, "run_id", "") == "run-5678"
        self.subscribed.append(observer)

    def unsubscribe(self, observer: object) -> None:
        self.unsubscribed.append(observer)


class FakeObserver:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id


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
            CommandAck(
                status=CommandAckStatus.ACCEPTED,
                run_id="run-5678",
                message="accepted",
            )
        )
        run_port = FakeRunPort()
        context = RunEventContext()
        context.activate_run(
            "run-1234",
            skill_name="wait_input_test",
            status=RunStatus.WAITING_INPUT,
        )
        use_case = SubmitWaitingInputUseCase(
            waiting_port=waiting_port,
            run_port=run_port,
            context=context,
        )
        observer = FakeObserver(run_id="run-1234")
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
        assert run_port.unsubscribed == [observer]
        assert run_port.subscribed == [observer]
        assert observer.run_id == "run-5678"
        assert result.state is state
        assert state.session_key == "run-5678"
        assert state.view_status.kind == ViewStatusKind.RUNNING
        assert context.run_id == "run-5678"
        assert context.skill_name == "wait_input_test"
        assert context.status == RunStatus.RUNNING
        assert state.prompt.waiting_prompt == ""
        assert state.prompt.text == ""
        assert state.prompt.cursor_position == 0
        assert isinstance(state.transcript.items[-2], UserInputItem)
        assert state.transcript.items[-2].text == "hello world"
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
            CommandAck(
                status=CommandAckStatus.REJECTED,
                message="error: input rejected",
            )
        )
        run_port = FakeRunPort()
        use_case = SubmitWaitingInputUseCase(
            waiting_port=waiting_port,
            run_port=run_port,
            context=RunEventContext(
                run_id="run-1234",
                skill_name="wait_input_test",
                status=RunStatus.WAITING_INPUT,
            ),
        )
        observer = FakeObserver(run_id="run-1234")
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
        assert run_port.subscribed == []
        assert run_port.unsubscribed == []
        assert observer.run_id == "run-1234"
        assert result.state is state
        assert state.view_status.kind == ViewStatusKind.ERROR
        assert isinstance(state.transcript.items[-2], UserInputItem)
        assert isinstance(state.transcript.items[-1], DispatchErrorItem)
        assert state.transcript.items[-1].message == "error: input rejected"

    asyncio.run(run())


def test_submit_waiting_input_use_case_ignores_missing_waiting_run() -> None:
    waiting_port = FakeWaitingPort(CommandAck(status=CommandAckStatus.ACCEPTED))
    run_port = FakeRunPort()
    use_case = SubmitWaitingInputUseCase(
        waiting_port=waiting_port,
        run_port=run_port,
        context=RunEventContext(),
    )
    observer = FakeObserver(run_id="")
    state = ConsoleScreenState(session_key="main")

    async def run() -> None:
        result = await use_case.execute(
            observer,
            state=state,
            text="hello",
        )

        assert result.state is state
        assert waiting_port.called_with == []
        assert run_port.subscribed == []
        assert run_port.unsubscribed == []
        assert state.transcript.items == []
        assert state.view_status.kind == ViewStatusKind.HIDDEN

    asyncio.run(run())
