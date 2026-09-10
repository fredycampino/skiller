from itertools import islice
from types import SimpleNamespace

import pytest

from skiller.application.observations.errors import ObserveRunError
from skiller.application.observations.models import (
    ObserveEvent,
    ObserveIdle,
    ObserveRunInput,
    ObserveRunSettings,
    ObserveStart,
    ObserveStop,
    ObserveWait,
    ObserveWaitType,
)
from skiller.application.use_cases.query.observe_run import ObserveRunUseCase
from skiller.application.waits.waiting_metadata_resolver import WaitingMetadataResolver
from skiller.domain.event.event_model import (
    RuntimeEvent,
    RuntimeEventType,
    RunWaitingPayload,
)
from skiller.domain.run.run_model import RunStatus
from skiller.domain.run.run_status_runtime_model import RunStatusRuntime

pytestmark = pytest.mark.unit


class _ScriptedRunStore:
    def __init__(
        self,
        statuses: list[RunStatusRuntime | None],
        *,
        run: object | None = None,
    ) -> None:
        self.statuses = list(statuses)
        self.run = run
        self.status_calls: list[str] = []
        self.run_calls: list[str] = []

    def get_status(self, run_id: str) -> RunStatusRuntime | None:
        self.status_calls.append(run_id)
        if len(self.statuses) == 1:
            return self.statuses[0]
        return self.statuses.pop(0)

    def get_run(self, run_id: str):  # noqa: ANN201
        self.run_calls.append(run_id)
        return self.run


class _ScriptedEventStore:
    def __init__(
        self,
        *,
        latest: list[RuntimeEvent | None],
        batches: list[list[RuntimeEvent]],
    ) -> None:
        self.latest = list(latest)
        self.batches = list(batches)
        self.list_calls: list[dict[str, object]] = []
        self.latest_calls: list[str] = []

    def get_last_event(self, run_id: str) -> RuntimeEvent | None:
        self.latest_calls.append(run_id)
        if len(self.latest) == 1:
            return self.latest[0]
        return self.latest.pop(0)

    def list_events(
        self,
        run_id: str,
        *,
        after_sequence: int | None = None,
        limit: int | None = None,
    ) -> list[RuntimeEvent]:
        self.list_calls.append(
            {
                "run_id": run_id,
                "after_sequence": after_sequence,
                "limit": limit,
            }
        )
        if len(self.batches) == 1:
            return list(self.batches[0])
        return list(self.batches.pop(0))


class _FakeRunner:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def render(self, step, context, *, flow):  # noqa: ANN001, ANN201
        self.calls.append({"step": step, "context": context, "flow": flow})
        rendered = dict(step)
        inputs = context.get("inputs", {})
        for key, value in inputs.items():
            token = "{{inputs." + str(key) + "}}"
            for field, raw_value in rendered.items():
                if isinstance(raw_value, str):
                    rendered[field] = raw_value.replace(token, str(value))
        return rendered


def _event(sequence: int, event_type: RuntimeEventType) -> RuntimeEvent:
    return RuntimeEvent(
        sequence=sequence,
        id=f"event-{sequence}",
        run_id="run-1",
        type=event_type,
        step_id="ask" if event_type == RuntimeEventType.RUN_WAITING else None,
        step_type="wait_input" if event_type == RuntimeEventType.RUN_WAITING else None,
        agent_sequence=None,
        created_at="2026-09-09 10:00:00",
        payload=RunWaitingPayload(output={}),
    )


def _status(status: RunStatus) -> RunStatusRuntime:
    return RunStatusRuntime(run_id="run-1", status=status)


def _waiting_run(step: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(
        status=RunStatus.WAITING.value,
        current="ask",
        snapshot={"steps": [step]},
        context=SimpleNamespace(to_dict=lambda: {"inputs": {"name": "Fede"}}),
    )


def _use_case(
    run_store: _ScriptedRunStore,
    event_store: _ScriptedEventStore,
    *,
    batch_size: int = 100,
    runner: _FakeRunner | None = None,
) -> ObserveRunUseCase:
    return ObserveRunUseCase(
        run_store=run_store,  # type: ignore[arg-type]
        event_store=event_store,  # type: ignore[arg-type]
        waiting_metadata_resolver=WaitingMetadataResolver(
            runner or _FakeRunner()  # type: ignore[arg-type]
        ),
        settings=ObserveRunSettings(batch_size=batch_size),
    )


def test_observe_drains_batches_and_stops_after_terminal_status() -> None:
    final_event = _event(3, RuntimeEventType.RUN_FINISHED)
    run_store = _ScriptedRunStore([_status(RunStatus.RUNNING), _status(RunStatus.SUCCEEDED)])
    event_store = _ScriptedEventStore(
        latest=[final_event, final_event],
        batches=[
            [_event(1, RuntimeEventType.RUN_CREATE), _event(2, RuntimeEventType.STEP_STARTED)],
            [final_event],
            [],
        ],
    )
    use_case = _use_case(run_store, event_store, batch_size=2)

    results = list(use_case.execute(ObserveRunInput(run_id="run-1", after=None, tail=100)))

    assert [type(result) for result in results] == [
        ObserveStart,
        ObserveEvent,
        ObserveEvent,
        ObserveEvent,
        ObserveStop,
    ]
    assert [call["after_sequence"] for call in event_store.list_calls] == [0, 2, 3]
    assert all(call["limit"] == 2 for call in event_store.list_calls)


def test_observe_waits_for_run_finished_after_terminal_status() -> None:
    last_non_terminal_event = _event(1, RuntimeEventType.STEP_SUCCESS)
    finished_event = _event(2, RuntimeEventType.RUN_FINISHED)
    run_store = _ScriptedRunStore(
        [
            _status(RunStatus.RUNNING),
            _status(RunStatus.SUCCEEDED),
            _status(RunStatus.SUCCEEDED),
        ]
    )
    event_store = _ScriptedEventStore(
        latest=[last_non_terminal_event, last_non_terminal_event, finished_event],
        batches=[[last_non_terminal_event], [], [finished_event], []],
    )

    results = list(
        _use_case(run_store, event_store).execute(
            ObserveRunInput(run_id="run-1", after=None, tail=100)
        )
    )

    assert [type(result) for result in results] == [
        ObserveStart,
        ObserveEvent,
        ObserveIdle,
        ObserveEvent,
        ObserveStop,
    ]


def test_observe_emits_wait_once_and_continues_after_resume() -> None:
    waiting_event = _event(2, RuntimeEventType.RUN_WAITING)
    finished_event = _event(4, RuntimeEventType.RUN_FINISHED)
    run = _waiting_run({"wait_input": "ask", "prompt": "Hello {{inputs.name}}"})
    run_store = _ScriptedRunStore(
        [
            _status(RunStatus.WAITING),
            _status(RunStatus.WAITING),
            _status(RunStatus.SUCCEEDED),
        ],
        run=run,
    )
    event_store = _ScriptedEventStore(
        latest=[waiting_event, waiting_event, finished_event],
        batches=[
            [_event(1, RuntimeEventType.RUN_CREATE), waiting_event],
            [],
            [],
            [_event(3, RuntimeEventType.RUN_RESUME), finished_event],
            [],
        ],
    )
    use_case = _use_case(run_store, event_store)

    results = list(use_case.execute(ObserveRunInput(run_id="run-1", after=None, tail=100)))

    assert [type(result) for result in results] == [
        ObserveStart,
        ObserveEvent,
        ObserveEvent,
        ObserveWait,
        ObserveIdle,
        ObserveEvent,
        ObserveEvent,
        ObserveStop,
    ]
    waiting = results[3]
    assert waiting == ObserveWait(
        sequence=2,
        wait_type=ObserveWaitType.INPUT,
        prompt="Hello Fede",
    )
    assert run_store.status_calls == ["run-1", "run-1", "run-1"]


def test_historical_wait_does_not_emit_wait_frame() -> None:
    finished_event = _event(3, RuntimeEventType.RUN_FINISHED)
    run_store = _ScriptedRunStore([_status(RunStatus.SUCCEEDED), _status(RunStatus.SUCCEEDED)])
    event_store = _ScriptedEventStore(
        latest=[finished_event, finished_event],
        batches=[
            [
                _event(1, RuntimeEventType.RUN_WAITING),
                _event(2, RuntimeEventType.RUN_RESUME),
                finished_event,
            ],
            [],
        ],
    )

    results = list(
        _use_case(run_store, event_store).execute(
            ObserveRunInput(run_id="run-1", after=None, tail=100)
        )
    )

    assert not any(isinstance(result, ObserveWait) for result in results)
    assert isinstance(results[-1], ObserveStop)


def test_channel_wait_produces_idle_instead_of_wait_frame() -> None:
    waiting_event = _event(1, RuntimeEventType.RUN_WAITING)
    run_store = _ScriptedRunStore(
        [_status(RunStatus.WAITING), _status(RunStatus.WAITING)],
        run=_waiting_run({"wait_channel": "ask", "channel": "chat", "key": "one"}),
    )
    event_store = _ScriptedEventStore(
        latest=[waiting_event, waiting_event],
        batches=[[waiting_event], []],
    )
    stream = _use_case(run_store, event_store).execute(
        ObserveRunInput(run_id="run-1", after=None, tail=100)
    )

    results = list(islice(stream, 3))

    assert [type(result) for result in results] == [
        ObserveStart,
        ObserveEvent,
        ObserveIdle,
    ]


def test_webhook_wait_emits_control_result_without_prompt() -> None:
    waiting_event = _event(1, RuntimeEventType.RUN_WAITING)
    run_store = _ScriptedRunStore(
        [_status(RunStatus.WAITING), _status(RunStatus.WAITING)],
        run=_waiting_run(
            {
                "wait_webhook": "ask",
                "webhook": "github",
                "key": "{{inputs.name}}",
            }
        ),
    )
    event_store = _ScriptedEventStore(
        latest=[waiting_event, waiting_event],
        batches=[[waiting_event], []],
    )
    stream = _use_case(run_store, event_store).execute(
        ObserveRunInput(run_id="run-1", after=None, tail=100)
    )

    results = list(islice(stream, 3))

    assert results[-1] == ObserveWait(
        sequence=1,
        wait_type=ObserveWaitType.WEBHOOK,
    )


def test_status_barrier_redrains_new_events_without_idle() -> None:
    first_event = _event(1, RuntimeEventType.RUN_CREATE)
    finished_event = _event(2, RuntimeEventType.RUN_FINISHED)
    run_store = _ScriptedRunStore(
        [
            _status(RunStatus.RUNNING),
            _status(RunStatus.SUCCEEDED),
        ]
    )
    event_store = _ScriptedEventStore(
        latest=[first_event, finished_event, finished_event],
        batches=[[first_event], [], [finished_event], []],
    )

    results = list(
        _use_case(run_store, event_store).execute(
            ObserveRunInput(run_id="run-1", after=None, tail=100)
        )
    )

    assert [type(result) for result in results] == [
        ObserveStart,
        ObserveEvent,
        ObserveEvent,
        ObserveStop,
    ]


def test_initial_tail_bounds_effective_cursor() -> None:
    finished_event = _event(150, RuntimeEventType.RUN_FINISHED)
    run_store = _ScriptedRunStore([_status(RunStatus.SUCCEEDED), _status(RunStatus.SUCCEEDED)])
    event_store = _ScriptedEventStore(
        latest=[finished_event, finished_event],
        batches=[[finished_event], []],
    )

    results = list(
        _use_case(run_store, event_store).execute(
            ObserveRunInput(run_id="run-1", after=None, tail=100)
        )
    )

    assert results[0] == ObserveStart(
        run_id="run-1",
        requested_after=None,
        effective_after=50,
        last_sequence=150,
        tail=100,
        truncated=True,
    )
    assert event_store.list_calls[0]["after_sequence"] == 50


def test_after_greater_than_last_sequence_is_rejected_before_event_read() -> None:
    last_event = _event(3, RuntimeEventType.STEP_STARTED)
    run_store = _ScriptedRunStore([_status(RunStatus.RUNNING)])
    event_store = _ScriptedEventStore(latest=[last_event], batches=[[]])
    stream = _use_case(run_store, event_store).execute(
        ObserveRunInput(run_id="run-1", after=4, tail=100)
    )

    with pytest.raises(ObserveRunError, match="exceeds last sequence"):
        next(stream)

    assert event_store.list_calls == []


def test_missing_run_is_rejected_before_start_result() -> None:
    run_store = _ScriptedRunStore([None])
    event_store = _ScriptedEventStore(latest=[None], batches=[[]])
    stream = _use_case(run_store, event_store).execute(
        ObserveRunInput(run_id="missing", after=None, tail=100)
    )

    with pytest.raises(ObserveRunError, match="not found"):
        next(stream)

    assert event_store.latest_calls == []


def test_invalid_event_sequence_fails() -> None:
    invalid_event = RuntimeEvent(
        sequence="1",  # type: ignore[arg-type]
        id="event-1",
        run_id="run-1",
        type=RuntimeEventType.RUN_CREATE,
        step_id=None,
        step_type=None,
        agent_sequence=None,
        created_at="2026-09-09 10:00:00",
        payload=RunWaitingPayload(output={}),
    )
    last_event = _event(1, RuntimeEventType.RUN_CREATE)
    run_store = _ScriptedRunStore([_status(RunStatus.RUNNING)])
    event_store = _ScriptedEventStore(
        latest=[last_event],
        batches=[[invalid_event]],
    )
    stream = _use_case(run_store, event_store).execute(
        ObserveRunInput(run_id="run-1", after=None, tail=100)
    )

    assert isinstance(next(stream), ObserveStart)
    with pytest.raises(ObserveRunError, match="event sequence"):
        next(stream)
