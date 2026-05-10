import pytest
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.steering_model import (
    SteeringAgentInterrupt,
    SteeringAgentMessage,
)
from skiller.infrastructure.db.sqlite_agent_steering_store import SqliteAgentSteeringStore
from skiller.infrastructure.db.sqlite_state_store import SqliteStateStore

pytestmark = pytest.mark.unit


def test_steering_queue_is_updated_only_through_agent_steering_store(tmp_path) -> None:
    db_path = tmp_path / "steering-queue.db"
    state_store = SqliteStateStore(str(db_path))
    steering_store = SqliteAgentSteeringStore(str(db_path))
    state_store.init_db()
    run_id = state_store.create_run(
        "internal",
        "demo",
        {"start": "show_message", "steps": [{"notify": "show_message"}]},
        RunContext(inputs={}, step_executions={}),
        run_id="550e8400-e29b-41d4-a716-446655440105",
    )

    steering_store.append(run_id, SteeringAgentInterrupt())
    steering_store.append(run_id, SteeringAgentMessage(text="be concise"))
    messages = steering_store.pop(run_id, SteeringAgentMessage)
    consumed = steering_store.pop(run_id, SteeringAgentInterrupt)
    run = state_store.get_run(run_id)

    assert messages == [SteeringAgentMessage(text="be concise")]
    assert consumed == [SteeringAgentInterrupt()]
    assert run is not None
    assert run.context.steering_queue == []


def test_agent_steering_store_raises_when_run_is_missing(tmp_path) -> None:
    db_path = tmp_path / "missing-run.db"
    state_store = SqliteStateStore(str(db_path))
    steering_store = SqliteAgentSteeringStore(str(db_path))
    state_store.init_db()
    with pytest.raises(ValueError, match="Run 'missing-run' not found"):
        steering_store.append("missing-run", SteeringAgentInterrupt())

    with pytest.raises(ValueError, match="Run 'missing-run' not found"):
        steering_store.pop("missing-run", SteeringAgentInterrupt)


def test_agent_steering_store_does_not_duplicate_pending_abort_turn(tmp_path) -> None:
    db_path = tmp_path / "dedupe-abort-turn.db"
    state_store = SqliteStateStore(str(db_path))
    steering_store = SqliteAgentSteeringStore(str(db_path))
    state_store.init_db()
    run_id = state_store.create_run(
        "internal",
        "demo",
        {"start": "show_message", "steps": [{"notify": "show_message"}]},
        RunContext(inputs={}, step_executions={}),
        run_id="550e8400-e29b-41d4-a716-446655440106",
    )

    steering_store.append(run_id, SteeringAgentInterrupt())
    steering_store.append(run_id, SteeringAgentInterrupt())
    run = state_store.get_run(run_id)

    assert run is not None
    assert run.context.steering_queue == [SteeringAgentInterrupt()]
