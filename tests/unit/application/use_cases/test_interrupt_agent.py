import pytest

from skiller.application.use_cases.agent.interrupt_agent import (
    InterruptAgentStatus,
    InterruptAgentUseCase,
)
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import Run
from skiller.domain.run.steering_model import SteeringAction, SteeringTarget

pytestmark = pytest.mark.unit


class _FakeStore:
    def __init__(self, run: Run | None) -> None:
        self.run = run
        self.calls: list[str] = []

    def get_run(self, run_id: str) -> Run | None:
        self.calls.append(run_id)
        return self.run


class _FakeAgentSteering:
    def __init__(self) -> None:
        self.enqueue_calls: list[tuple[str, object]] = []

    def enqueue(self, run_id: str, item) -> None:  # noqa: ANN001
        self.enqueue_calls.append((run_id, item))


def _build_run() -> Run:
    return Run(
        id="run-1",
        skill_source="internal",
        skill_ref="demo",
        skill_snapshot={"start": "agent", "steps": []},
        status="RUNNING",
        current="agent",
        context=RunContext(inputs={}, step_executions={}),
        created_at="2026-05-05T10:00:00Z",
        updated_at="2026-05-05T10:00:00Z",
    )


def test_interrupt_agent_enqueues_abort_turn() -> None:
    store = _FakeStore(_build_run())
    steering = _FakeAgentSteering()
    use_case = InterruptAgentUseCase(store=store, agent_steering=steering)

    result = use_case.execute("run-1")

    assert result.status == InterruptAgentStatus.ENQUEUED
    assert result.run_id == "run-1"
    assert result.item is not None
    assert result.item.target == SteeringTarget.AGENT
    assert result.item.action == SteeringAction.ABORT_TURN
    assert steering.enqueue_calls == [("run-1", result.item)]


def test_interrupt_agent_rejects_empty_run_id() -> None:
    use_case = InterruptAgentUseCase(
        store=_FakeStore(_build_run()),
        agent_steering=_FakeAgentSteering(),
    )

    result = use_case.execute("   ")

    assert result.status == InterruptAgentStatus.INVALID_RUN_ID
    assert result.error == "run_id is required"


def test_interrupt_agent_returns_not_found_when_run_is_missing() -> None:
    store = _FakeStore(None)
    steering = _FakeAgentSteering()
    use_case = InterruptAgentUseCase(store=store, agent_steering=steering)

    result = use_case.execute("missing-run")

    assert result.status == InterruptAgentStatus.RUN_NOT_FOUND
    assert result.error == "Run 'missing-run' not found"
    assert steering.enqueue_calls == []
