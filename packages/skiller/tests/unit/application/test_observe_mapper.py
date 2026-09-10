import pytest

from skiller.application.observations.mapper import ObserveRunMapper
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
from skiller.domain.event.event_model import (
    RuntimeEvent,
    RuntimeEventType,
    RunWaitingPayload,
)
from skiller.domain.run.run_model import RunStatus

pytestmark = pytest.mark.unit


def _event(sequence: int) -> RuntimeEvent:
    return RuntimeEvent(
        sequence=sequence,
        id=f"event-{sequence}",
        run_id="run-1",
        type=RuntimeEventType.RUN_WAITING,
        step_id="ask",
        step_type="wait_input",
        agent_sequence=None,
        created_at="2026-09-09 10:00:00",
        payload=RunWaitingPayload(output={}),
    )


def test_mapper_normalizes_and_validates_observe_input() -> None:
    mapper = ObserveRunMapper(ObserveRunSettings(default_tail=25, max_tail=50))

    request = mapper.to_observe_input(" run-1 ", after=3, tail=None)

    assert request == ObserveRunInput(run_id="run-1", after=3, tail=25)

    with pytest.raises(ValueError, match="RUN_ID is required"):
        mapper.to_observe_input(" ", after=None, tail=10)
    with pytest.raises(ValueError, match="--after"):
        mapper.to_observe_input("run-1", after=-1, tail=10)
    with pytest.raises(ValueError, match="--tail"):
        mapper.to_observe_input("run-1", after=None, tail=51)


def test_mapper_builds_the_public_frame_contract() -> None:
    mapper = ObserveRunMapper(ObserveRunSettings())

    frames = [
        mapper.to_frame(
            ObserveStart(
                run_id="run-1",
                requested_after=10,
                effective_after=40,
                last_sequence=140,
                tail=100,
                truncated=True,
            )
        ),
        mapper.to_frame(ObserveEvent(event=_event(41))),
        mapper.to_frame(
            ObserveWait(
                sequence=80,
                wait_type=ObserveWaitType.INPUT,
                prompt="Write a value",
            )
        ),
        mapper.to_frame(
            ObserveWait(
                sequence=90,
                wait_type=ObserveWaitType.WEBHOOK,
            )
        ),
        mapper.to_frame(ObserveStop(sequence=100, status=RunStatus.SUCCEEDED)),
    ]

    assert frames[0] == {
        "kind": "start",
        "version": 1,
        "run_id": "run-1",
        "requested_after": 10,
        "effective_after": 40,
        "last_sequence": 140,
        "tail": 100,
        "truncated": True,
    }
    assert frames[1] == {
        "kind": "event",
        "event": _event(41).model_dump(mode="json"),
    }
    assert frames[2] == {
        "kind": "wait",
        "sequence": 80,
        "wait_type": "input",
        "prompt": "Write a value",
    }
    assert frames[3] == {
        "kind": "wait",
        "sequence": 90,
        "wait_type": "webhook",
    }
    assert frames[4] == {
        "kind": "stop",
        "sequence": 100,
        "status": "succeeded",
    }
    assert mapper.to_frame(ObserveIdle()) is None
