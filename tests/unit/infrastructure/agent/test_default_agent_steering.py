import pytest

from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import Run
from skiller.domain.run.steering_model import (
    SteeringAction,
    SteeringItem,
    SteeringTarget,
)
from skiller.infrastructure.agent.default_agent_steering import DefaultAgentSteering

pytestmark = pytest.mark.unit


class _FakeStore:
    def __init__(self, run: Run | None) -> None:
        self.run = run
        self.updated_contexts: list[RunContext] = []

    def get_run(self, run_id: str) -> Run | None:
        return self.run

    def update_run(self, run_id: str, *, status=None, current=None, context=None) -> None:  # noqa: ANN001
        if self.run is None or context is None:
            return
        self.run.context = context
        self.updated_contexts.append(context)


def _build_run(*, steering_queue: list[SteeringItem] | None = None) -> Run:
    return Run(
        id="run-1",
        skill_source="internal",
        skill_ref="demo",
        skill_snapshot={"start": "step-1", "steps": []},
        status="RUNNING",
        current="step-1",
        context=RunContext(
            inputs={},
            step_executions={},
            steering_queue=list(steering_queue or []),
        ),
        created_at="2026-05-05T10:00:00Z",
        updated_at="2026-05-05T10:00:00Z",
    )


def test_enqueue_appends_item_and_persists_context() -> None:
    store = _FakeStore(_build_run())
    steering = DefaultAgentSteering(store)
    item = SteeringItem(
        target=SteeringTarget.AGENT,
        action=SteeringAction.STEERING_MESSAGE,
        text="change this",
    )

    steering.enqueue("run-1", item)

    assert store.run is not None
    assert store.run.context.steering_queue == [item]
    assert len(store.updated_contexts) == 1


def test_consume_abort_turn_removes_first_abort_and_persists() -> None:
    store = _FakeStore(
        _build_run(
            steering_queue=[
                SteeringItem(
                    target=SteeringTarget.AGENT,
                    action=SteeringAction.ABORT_TURN,
                ),
                SteeringItem(
                    target=SteeringTarget.AGENT,
                    action=SteeringAction.STEERING_MESSAGE,
                    text="keep me",
                ),
            ]
        )
    )
    steering = DefaultAgentSteering(store)

    consumed = steering.consume_abort_turn("run-1")

    assert consumed is True
    assert store.run is not None
    assert store.run.context.steering_queue == [
        SteeringItem(
            target=SteeringTarget.AGENT,
            action=SteeringAction.STEERING_MESSAGE,
            text="keep me",
        )
    ]
    assert len(store.updated_contexts) == 1


def test_pop_steering_messages_returns_messages_and_keeps_other_items() -> None:
    store = _FakeStore(
        _build_run(
            steering_queue=[
                SteeringItem(
                    target=SteeringTarget.AGENT,
                    action=SteeringAction.STEERING_MESSAGE,
                    text="first",
                ),
                SteeringItem(
                    target=SteeringTarget.AGENT,
                    action=SteeringAction.ABORT_TURN,
                ),
                SteeringItem(
                    target=SteeringTarget.AGENT,
                    action=SteeringAction.STEERING_MESSAGE,
                    text="second",
                ),
            ]
        )
    )
    steering = DefaultAgentSteering(store)

    messages = steering.pop_steering_messages("run-1")

    assert messages == ["first", "second"]
    assert store.run is not None
    assert store.run.context.steering_queue == [
        SteeringItem(
            target=SteeringTarget.AGENT,
            action=SteeringAction.ABORT_TURN,
        )
    ]
    assert len(store.updated_contexts) == 1


def test_operations_raise_when_run_is_missing() -> None:
    steering = DefaultAgentSteering(_FakeStore(None))
    item = SteeringItem(
        target=SteeringTarget.AGENT,
        action=SteeringAction.STEERING_MESSAGE,
        text="change this",
    )

    with pytest.raises(ValueError, match="Run 'run-1' not found"):
        steering.enqueue("run-1", item)

    with pytest.raises(ValueError, match="Run 'run-1' not found"):
        steering.consume_abort_turn("run-1")

    with pytest.raises(ValueError, match="Run 'run-1' not found"):
        steering.pop_steering_messages("run-1")
