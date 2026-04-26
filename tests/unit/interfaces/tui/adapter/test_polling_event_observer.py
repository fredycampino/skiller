from __future__ import annotations

import asyncio

import pytest

import skiller.interfaces.tui.adapter.polling_event_observer as polling_module
from skiller.interfaces.tui.adapter.polling_event_observer import (
    PollingEventObserver,
)
from skiller.interfaces.tui.adapter.run_event_mapper import RunEventMapper
from skiller.interfaces.tui.port.run_port import ObserverType, PollingEventKind

pytestmark = pytest.mark.unit


class FakeRunObserver:
    type = ObserverType.RUN

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.events: list[object] = []

    def notify(self, events) -> None:  # noqa: ANN001
        self.events.extend(events)


def test_polling_event_observer_subscribes_and_notifies_run_observer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_sleep = asyncio.sleep
    status_payloads = iter(
        [
            {"id": "run-1234", "status": "RUNNING"},
            {"id": "run-1234", "status": "SUCCEEDED"},
        ]
    )
    log_payloads = iter(
        [
            [
                {
                    "id": "evt-1",
                    "type": "STEP_STARTED",
                    "payload": {"step": "notify", "step_type": "tool"},
                }
            ],
            [
                {
                    "id": "evt-1",
                    "type": "STEP_STARTED",
                    "payload": {"step": "notify", "step_type": "tool"},
                },
                {
                    "id": "evt-2",
                    "type": "STEP_SUCCESS",
                    "payload": {
                        "step": "notify",
                        "step_type": "tool",
                        "output": "ok",
                        "next": "done",
                    },
                },
            ],
        ]
    )

    def fake_run_json_command(*args: str):  # noqa: ANN001
        assert args == ("status", "run-1234")
        return next(status_payloads)

    def fake_run_json_list_command(*args: str):  # noqa: ANN001
        assert args == ("logs", "run-1234")
        return next(log_payloads)

    async def fake_to_thread(function, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return function(*args, **kwargs)

    async def fake_sleep(_seconds: float) -> None:
        await original_sleep(0)

    monkeypatch.setattr(polling_module, "_run_json_command", fake_run_json_command)
    monkeypatch.setattr(polling_module, "_run_json_list_command", fake_run_json_list_command)
    monkeypatch.setattr(polling_module.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(polling_module.asyncio, "sleep", fake_sleep)

    async def run() -> None:
        event_observer = PollingEventObserver(interval_seconds=0.0)
        run_observer = FakeRunObserver("run-1234")
        event_observer.subscribe(run_observer)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert [event.kind for event in run_observer.events] == [
            PollingEventKind.LOG,
            PollingEventKind.STATUS,
            PollingEventKind.LOG,
            PollingEventKind.STATUS,
        ]
        assert run_observer.events[0].event_type == "STEP_STARTED"
        assert run_observer.events[0].step == "notify"
        assert run_observer.events[0].step_type == "tool"
        assert run_observer.events[1].status == "RUNNING"
        assert run_observer.events[2].event_type == "STEP_SUCCESS"
        assert run_observer.events[2].output == '"ok"'
        assert run_observer.events[3].status == "SUCCEEDED"
        event_observer.unsubscribe(run_observer)

    asyncio.run(run())


def test_run_event_mapper_converts_payloads() -> None:
    mapper = RunEventMapper()
    seen_event_ids = {"evt-1"}

    log_events = mapper.logs_to_events(
        run_id="run-1234",
        events_payload=[
            {"id": "evt-1", "type": "STEP_STARTED", "payload": {"step": "ignored"}},
            {
                "id": "evt-2",
                "type": "STEP_SUCCESS",
                "payload": {"step": "notify", "step_type": "tool", "output": "ok"},
            },
        ],
        seen_event_ids=seen_event_ids,
    )
    status_event = mapper.status_to_event(
        run_id="run-1234",
        status_payload={"status": "RUNNING"},
        last_status="CREATED",
    )

    assert [event.kind for event in log_events] == [PollingEventKind.LOG]
    assert log_events[0].event_id == "evt-2"
    assert log_events[0].event_type == "STEP_SUCCESS"
    assert log_events[0].step == "notify"
    assert log_events[0].step_type == "tool"
    assert log_events[0].output == '"ok"'
    assert status_event is not None
    assert status_event.kind == PollingEventKind.STATUS
    assert status_event.status == "RUNNING"
