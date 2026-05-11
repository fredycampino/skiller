from __future__ import annotations

import asyncio

import pytest
from stui.adapter.polling_event_observer import (
    PollingEventObserver,
)
from stui.adapter.run_event_mapper import RunEventMapper
from stui.port.run_port import ObserverType, PollingEventKind

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
            {"id": "run-1234", "status": "SUCCEEDED", "last_event_sequence": 2},
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

    async def run() -> None:
        event_observer = PollingEventObserver(interval_seconds=0.0)
        monkeypatch.setattr(event_observer, "_run_json_command", fake_run_json_command)
        monkeypatch.setattr(event_observer, "_run_json_list_command", fake_run_json_list_command)
        monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)
        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
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


def test_polling_event_observer_waits_until_logs_reach_terminal_status_sequence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_sleep = asyncio.sleep
    status_payloads = iter(
        [
            {"id": "run-1234", "status": "RUNNING"},
            {
                "id": "run-1234",
                "status": "WAITING",
                "last_event_sequence": 4,
                "last_event_type": "RUN_WAITING",
            },
            {
                "id": "run-1234",
                "status": "WAITING",
                "last_event_sequence": 4,
                "last_event_type": "RUN_WAITING",
            },
        ]
    )
    log_payloads = iter(
        [
            [
                {
                    "id": "evt-1",
                    "type": "STEP_STARTED",
                    "payload": {"step": "ci_agent", "step_type": "agent", "sequence": 1},
                }
            ],
            [
                {
                    "id": "evt-2",
                    "type": "STEP_SUCCESS",
                    "payload": {
                        "step": "ci_agent",
                        "step_type": "agent",
                        "output": {"text": "done"},
                        "sequence": 2,
                    },
                }
            ],
            [
                {
                    "id": "evt-3",
                    "type": "STEP_STARTED",
                    "payload": {"step": "ask_user", "step_type": "wait_input", "sequence": 3},
                },
                {
                    "id": "evt-4",
                    "type": "RUN_WAITING",
                    "payload": {
                        "step": "ask_user",
                        "step_type": "wait_input",
                        "output": {"text": "Write a message."},
                        "sequence": 4,
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

    async def run() -> None:
        event_observer = PollingEventObserver(interval_seconds=0.0)
        monkeypatch.setattr(event_observer, "_run_json_command", fake_run_json_command)
        monkeypatch.setattr(event_observer, "_run_json_list_command", fake_run_json_list_command)
        monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)
        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
        run_observer = FakeRunObserver("run-1234")
        event_observer.subscribe(run_observer)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert [event.kind for event in run_observer.events] == [
            PollingEventKind.LOG,
            PollingEventKind.STATUS,
            PollingEventKind.LOG,
            PollingEventKind.STATUS,
            PollingEventKind.LOG,
            PollingEventKind.LOG,
        ]
        assert run_observer.events[3].status == "WAITING"
        assert run_observer.events[3].last_event_sequence == 4
        assert run_observer.events[4].sequence == 3
        assert run_observer.events[5].sequence == 4
        event_observer.unsubscribe(run_observer)

    asyncio.run(run())


def test_polling_event_observer_waits_for_matching_terminal_event_type_when_sequence_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_sleep = asyncio.sleep
    status_payloads = iter(
        [
            {
                "id": "run-1234",
                "status": "WAITING",
                "last_event_sequence": 4,
                "last_event_type": "RUN_WAITING",
            },
            {
                "id": "run-1234",
                "status": "WAITING",
                "last_event_sequence": 4,
                "last_event_type": "RUN_WAITING",
            },
        ]
    )
    log_payloads = iter(
        [
            [
                {
                    "id": "evt-4a",
                    "type": "STEP_STARTED",
                    "payload": {"step": "ask_user", "step_type": "wait_input", "sequence": 4},
                },
            ],
            [
                {
                    "id": "evt-4b",
                    "type": "RUN_WAITING",
                    "payload": {
                        "step": "ask_user",
                        "step_type": "wait_input",
                        "output": {"text": "Write a message."},
                        "sequence": 4,
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

    async def run() -> None:
        event_observer = PollingEventObserver(interval_seconds=0.0)
        monkeypatch.setattr(event_observer, "_run_json_command", fake_run_json_command)
        monkeypatch.setattr(event_observer, "_run_json_list_command", fake_run_json_list_command)
        monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)
        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
        run_observer = FakeRunObserver("run-1234")
        event_observer.subscribe(run_observer)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert [event.kind for event in run_observer.events] == [
            PollingEventKind.LOG,
            PollingEventKind.STATUS,
            PollingEventKind.LOG,
        ]
        assert run_observer.events[0].event_type == "STEP_STARTED"
        assert run_observer.events[0].sequence == 4
        assert run_observer.events[1].last_event_type == "RUN_WAITING"
        assert run_observer.events[2].event_type == "RUN_WAITING"
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
        status_payload={"status": "RUNNING", "prompt": "Write a message"},
        last_status="CREATED",
        last_event_sequence=None,
        last_event_type="",
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
    assert status_event.prompt == "Write a message"


def test_run_event_mapper_emits_status_when_last_event_sequence_changes() -> None:
    mapper = RunEventMapper()

    status_event = mapper.status_to_event(
        run_id="run-1234",
        status_payload={
            "status": "WAITING",
            "prompt": "Write a message",
            "last_event_sequence": 11,
            "last_event_type": "RUN_WAITING",
        },
        last_status="WAITING",
        last_event_sequence=10,
        last_event_type="STEP_STARTED",
    )

    assert status_event is not None
    assert status_event.status == "WAITING"
    assert status_event.last_event_sequence == 11
    assert status_event.last_event_type == "RUN_WAITING"


def test_run_event_mapper_emits_status_when_last_event_type_changes() -> None:
    mapper = RunEventMapper()

    status_event = mapper.status_to_event(
        run_id="run-1234",
        status_payload={
            "status": "WAITING",
            "prompt": "Write a message",
            "last_event_sequence": 11,
            "last_event_type": "RUN_WAITING",
        },
        last_status="WAITING",
        last_event_sequence=11,
        last_event_type="STEP_STARTED",
    )

    assert status_event is not None
    assert status_event.last_event_sequence == 11
    assert status_event.last_event_type == "RUN_WAITING"


def test_run_event_mapper_keeps_agent_assistant_message_fields() -> None:
    mapper = RunEventMapper()

    log_events = mapper.logs_to_events(
        run_id="run-1234",
        events_payload=[
            {
                "id": "evt-200",
                "type": "AGENT_ASSISTANT_MESSAGE",
                "payload": {
                    "step": "support_agent",
                    "step_type": "agent",
                    "turn_id": "turn-1",
                    "sequence": 32,
                    "message_type": "tool_calls",
                    "text": "I will inspect the repository state.",
                },
            },
        ],
        seen_event_ids=set(),
    )

    assert len(log_events) == 1
    assert log_events[0].event_type == "AGENT_ASSISTANT_MESSAGE"
    assert log_events[0].step == "support_agent"
    assert log_events[0].step_type == "agent"
    assert log_events[0].turn_id == "turn-1"
    assert log_events[0].sequence == 32
    assert log_events[0].message_type == "tool_calls"
    assert log_events[0].assistant_text == "I will inspect the repository state."


def test_run_event_mapper_keeps_full_output_payload_without_truncation() -> None:
    mapper = RunEventMapper()

    long_text = "x" * 300
    output_payload = {
        "body_ref": None,
        "text": long_text,
        "value": {"payload": {"text": long_text}},
    }
    log_events = mapper.logs_to_events(
        run_id="run-1234",
        events_payload=[
            {
                "id": "evt-99",
                "type": "STEP_SUCCESS",
                "payload": {
                    "step": "ask_user",
                    "step_type": "wait_input",
                    "output": output_payload,
                },
            },
        ],
        seen_event_ids=set(),
    )

    assert len(log_events) == 1
    assert "..." not in log_events[0].output
    assert long_text in log_events[0].output


def test_run_event_mapper_ignores_succeeded_run_finished_event() -> None:
    mapper = RunEventMapper()

    log_events = mapper.logs_to_events(
        run_id="run-1234",
        events_payload=[
            {
                "id": "evt-100",
                "type": "RUN_FINISHED",
                "payload": {
                    "status": "SUCCEEDED",
                    "error": "",
                },
            },
        ],
        seen_event_ids=set(),
    )

    assert log_events == []
