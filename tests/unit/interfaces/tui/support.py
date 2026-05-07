from __future__ import annotations

from contextlib import contextmanager
from types import ModuleType
from typing import Iterator

from skiller.interfaces.tui.di.container import build_tui_container
from skiller.interfaces.tui.port.run_port import PollingEvent, PollingEventKind
from skiller.interfaces.tui.port.runs_port import RunsPortItem
from skiller.interfaces.tui.viewmodel.console_screen_viewmodel import (
    ConsoleScreenViewModel,
)


async def immediate_to_thread(function, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
    return function(*args, **kwargs)


def build_viewmodel(
    *,
    session_key: str = "main",
    run_port,
    waiting_port,
    runs_port=None,
    agent_port=None,
) -> ConsoleScreenViewModel:
    container = build_tui_container(
        run_port=run_port,
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

    def subscribe(self, observer: object) -> None:
        _ = observer

    def unsubscribe(self, observer: object) -> None:
        _ = observer


class ActivatingRunPort:
    def __init__(self) -> None:
        self.subscribed: list[object] = []
        self.unsubscribed: list[object] = []

    def run(self, raw_args: str):  # noqa: ANN001
        raise AssertionError(f"unexpected run call: {raw_args}")

    def subscribe(self, observer: object) -> None:
        self.subscribed.append(observer)
        notify = getattr(observer, "notify", None)
        if callable(notify):
            notify(
                [
                    PollingEvent(
                        kind=PollingEventKind.LOG,
                        run_id="run-1234",
                        event_type="RUN_WAITING",
                        step="ask_user",
                        step_type="wait_input",
                        output=(
                            '{"text":"Write a message.",'
                            '"value":{"prompt":"Write a message."},"body_ref":null}'
                        ),
                    ),
                    PollingEvent(
                        kind=PollingEventKind.STATUS,
                        run_id="run-1234",
                        status="WAITING",
                        prompt="Write a message.",
                    ),
                ]
            )

    def unsubscribe(self, observer: object) -> None:
        self.unsubscribed.append(observer)


class NeverCalledWaitingPort:
    def send_input(self, *, run_id: str, text: str):  # noqa: ANN001
        raise AssertionError(f"unexpected send_input call: {run_id} {text}")
