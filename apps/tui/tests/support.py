from __future__ import annotations

from contextlib import contextmanager
from types import ModuleType
from typing import Iterator

from stui.di.container import build_tui_container
from stui.port.run_port import (
    CommandAck,
    CommandAckStatus,
    RunRuntimeStatus,
)
from stui.port.runs_port import RunsPortItem
from stui.viewmodel.console_screen_viewmodel import (
    ConsoleScreenViewModel,
)


async def immediate_to_thread(function, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
    return function(*args, **kwargs)


def build_viewmodel(
    *,
    session_key: str = "main",
    run_port,
    events_port=None,
    waiting_port,
    runs_port=None,
    agent_port=None,
) -> ConsoleScreenViewModel:
    resolved_events_port = events_port or FakeEventsPort()
    container = build_tui_container(
        run_port=run_port,
        events_port=resolved_events_port,
        runs_port=runs_port,
        waiting_port=waiting_port,
        agent_port=agent_port,
    )
    return container.build_viewmodel(session_key=session_key)


@contextmanager
def patched_to_thread(*modules: ModuleType) -> Iterator[None]:
    originals = [(module, module.asyncio.to_thread) for module in modules]
    for module, _ in originals:
        module.asyncio.to_thread = immediate_to_thread
    try:
        yield
    finally:
        for module, original in originals:
            module.asyncio.to_thread = original


def make_runs_port_item(
    *,
    run_id: str = "run-1",
    skill_ref: str = "chat",
    status: str = "WAITING",
    current: str = "ask_user",
    wait_type: str | None = None,
) -> RunsPortItem:
    return RunsPortItem(
        id=run_id,
        skill_source="internal",
        skill_ref=skill_ref,
        status=status,
        current=current,
        created_at="2026-05-04 00:00:00",
        updated_at="2026-05-04 00:00:01",
        wait_type=wait_type,
    )


class FakeRunsPort:
    def __init__(
        self,
        runs: list[RunsPortItem] | None = None,
        error: RuntimeError | None = None,
    ) -> None:
        self.runs = runs or [make_runs_port_item()]
        self.error = error
        self.called_with: list[tuple[int, list[str] | None]] = []

    def list_runs(
        self,
        *,
        limit: int = 20,
        statuses: list[str] | None = None,
    ) -> list[RunsPortItem]:
        self.called_with.append((limit, list(statuses) if statuses is not None else None))
        if self.error is not None:
            raise self.error
        return list(self.runs)


class NeverCalledRunPort:
    def run(self, raw_args: str):  # noqa: ANN001
        raise AssertionError(f"unexpected run call: {raw_args}")

    def status(self, run_id: str) -> RunRuntimeStatus | None:
        _ = run_id
        return None

class NeverCalledWaitingPort:
    def send_input(self, *, run_id: str, text: str):  # noqa: ANN001
        raise AssertionError(f"unexpected send_input call: {run_id} {text}")


class FakeAgentPort:
    def __init__(self, ack: CommandAck | None = None) -> None:
        self.ack = ack or CommandAck(status=CommandAckStatus.ACCEPTED, message="accepted")
        self.called_with: list[str] = []

    def interrupt(self, run_id: str) -> CommandAck:
        self.called_with.append(run_id)
        return self.ack


class FakeEventsPort:
    def __init__(self, *, current_run_id: str = "", current_listener: object | None = None) -> None:
        self.subscribe_calls: list[str] = []
        self.unsubscribe_call_count = 0
        self.current_run_id = current_run_id
        self.current_listener = current_listener

    def subscribe(self, *, run_id: str, listener: object) -> None:
        if self.current_listener is not None:
            self.unsubscribe()
        self.current_listener = listener
        self.current_run_id = run_id
        self.subscribe_calls.append(run_id)

    def unsubscribe(self) -> None:
        self.unsubscribe_call_count += 1
        self.current_listener = None
        self.current_run_id = ""
