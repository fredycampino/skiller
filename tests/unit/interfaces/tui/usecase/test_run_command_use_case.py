from __future__ import annotations

import asyncio

import pytest

import skiller.interfaces.tui.usecase.run_command_use_case as run_command_use_case_module
from skiller.interfaces.tui.port.run_port import CommandAck, CommandAckStatus
from skiller.interfaces.tui.usecase.normalize_command_use_case import (
    NormalizeCommandUseCase,
)
from skiller.interfaces.tui.usecase.run_command_use_case import RunCommandUseCase
from skiller.interfaces.tui.usecase.run_event_context import (
    RunEventContext,
    RunStatus,
)
from skiller.interfaces.tui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    DispatchErrorItem,
    RunAckItem,
    TranscriptMode,
    UserInputItem,
    ViewStatusKind,
)

pytestmark = pytest.mark.unit


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
        assert getattr(observer, "run_id", "") == "run-1234"
        self.subscribed.append(observer)

    def unsubscribe(self, observer: object) -> None:
        self.unsubscribed.append(observer)


class FakeObserver:
    def __init__(self, run_id: str = "") -> None:
        self.run_id = run_id


def test_run_command_use_case_dispatches_normalized_args(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_to_thread(function, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return function(*args, **kwargs)

    monkeypatch.setattr(run_command_use_case_module.asyncio, "to_thread", fake_to_thread)

    async def run() -> None:
        port = FakeRunPort(
            CommandAck(
                status=CommandAckStatus.ACCEPTED,
                run_id="run-1234",
                message="[run-dispatch] chat:1234\n  ↳ created",
            )
        )
        context = RunEventContext()
        use_case = RunCommandUseCase(run_port=port, context=context)
        state = ConsoleScreenState(session_key="main")
        observer = FakeObserver(run_id="")

        result = await use_case.execute(
            observer,
            state=state,
            command=NormalizeCommandUseCase().execute(text="/run   chat  "),
        )

        assert port.called_with == ["chat"]
        assert port.subscribed == [observer]
        assert port.unsubscribed == []
        assert observer.run_id == "run-1234"
        assert result.state is state
        assert result.raw_args == "chat"
        assert result.ack.status == CommandAckStatus.ACCEPTED
        assert result.ack.run_id == "run-1234"
        assert context.run_id == "run-1234"
        assert context.skill_name == "chat"
        assert context.status == RunStatus.RUNNING
        assert state.session_key == "run-1234"
        assert state.view_status.kind == ViewStatusKind.RUNNING
        assert state.prompt.text == ""
        assert state.prompt.cursor_position == 0
        assert isinstance(state.transcript.items[-2], UserInputItem)
        assert isinstance(state.transcript.items[-1], RunAckItem)
        assert state.transcript.items[-1].skill == "chat"
        assert state.transcript.items[-1].run_id == "run-1234"

    asyncio.run(run())


def test_run_command_use_case_sets_chat_transcript_mode_for_chat_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_to_thread(function, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return function(*args, **kwargs)

    monkeypatch.setattr(run_command_use_case_module.asyncio, "to_thread", fake_to_thread)

    async def run() -> None:
        port = FakeRunPort(
            CommandAck(
                status=CommandAckStatus.ACCEPTED,
                run_id="run-1234",
                message="accepted",
            )
        )
        context = RunEventContext()
        use_case = RunCommandUseCase(run_port=port, context=context)
        state = ConsoleScreenState(session_key="main")
        observer = FakeObserver(run_id="")

        await use_case.execute(
            observer,
            state=state,
            command=NormalizeCommandUseCase().execute(text="/chat agent_tools"),
        )

        assert state.transcript.mode == TranscriptMode.CHAT
        assert port.called_with == ["agent_tools"]

    asyncio.run(run())


def test_run_command_use_case_records_dispatch_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_to_thread(function, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return function(*args, **kwargs)

    monkeypatch.setattr(run_command_use_case_module.asyncio, "to_thread", fake_to_thread)

    async def run() -> None:
        port = FakeRunPort(
            CommandAck(
                status=CommandAckStatus.ERROR,
                message="error: boom",
            )
        )
        context = RunEventContext()
        use_case = RunCommandUseCase(run_port=port, context=context)
        state = ConsoleScreenState(session_key="main")
        observer = FakeObserver(run_id="run-previous")

        result = await use_case.execute(
            observer,
            state=state,
            command=NormalizeCommandUseCase().execute(text="/run chat"),
        )

        assert port.called_with == ["chat"]
        assert port.unsubscribed == []
        assert port.subscribed == []
        assert observer.run_id == "run-previous"
        assert result.state is state
        assert result.raw_args == "chat"
        assert result.ack.status == CommandAckStatus.ERROR
        assert context.run_id == ""
        assert context.skill_name == ""
        assert context.status is None
        assert state.session_key == "main"
        assert state.view_status.kind == ViewStatusKind.ERROR
        assert isinstance(state.transcript.items[-2], UserInputItem)
        assert isinstance(state.transcript.items[-1], DispatchErrorItem)
        assert state.transcript.items[-1].message == "error: boom"

    asyncio.run(run())
