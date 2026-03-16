import pytest

from skiller.application.use_cases.execute_notify_step import ExecuteNotifyStepUseCase
from skiller.application.use_cases.render_current_step import CurrentStep, StepType
from skiller.application.use_cases.step_execution_result import StepExecutionStatus
from skiller.domain.run_context_model import RunContext
from skiller.domain.run_model import RunStatus

pytestmark = pytest.mark.unit


class _FakeStore:
    def __init__(self) -> None:
        self.updated_runs: list[dict[str, object]] = []
        self.events: list[dict[str, object]] = []

    def update_run(self, run_id: str, *, status=None, current=None, context=None) -> None:  # noqa: ANN001
        self.updated_runs.append(
            {
                "run_id": run_id,
                "status": status,
                "current": current,
                "context": context,
            }
        )

    def append_event(
        self, event_type: str, payload: dict[str, object], run_id: str | None = None
    ) -> str:
        self.events.append({"type": event_type, "payload": payload, "run_id": run_id})
        return "event-1"


def _build_next_step(step: dict[str, object]) -> CurrentStep:
    return CurrentStep(
        run_id="run-1",
        step_index=0,
        step_id=str(step["id"]),
        step_type=StepType.NOTIFY,
        step=step,
        context=RunContext(inputs={}, results={}),
    )


def test_notify_moves_current_to_explicit_next() -> None:
    store = _FakeStore()
    use_case = ExecuteNotifyStepUseCase(store=store)
    next_step = _build_next_step({"id": "start", "type": "notify", "message": "ok", "next": "done"})

    result = use_case.execute(next_step)

    assert result.status == StepExecutionStatus.NEXT
    assert result.next_step_id == "done"
    assert next_step.context.results["start"] == {"ok": True, "message": "ok"}
    assert store.updated_runs == [
        {
            "run_id": "run-1",
            "status": RunStatus.RUNNING,
            "current": "done",
            "context": next_step.context,
        }
    ]
    assert store.events == [
        {
            "type": "NOTIFY",
            "payload": {"step": "start", "message": "ok"},
            "run_id": "run-1",
        }
    ]


def test_notify_marks_completed_when_next_is_missing() -> None:
    store = _FakeStore()
    use_case = ExecuteNotifyStepUseCase(store=store)
    next_step = _build_next_step({"id": "start", "type": "notify", "message": "ok"})

    result = use_case.execute(next_step)

    assert result.status == StepExecutionStatus.COMPLETED
    assert result.next_step_id is None
    assert store.updated_runs == [
        {
            "run_id": "run-1",
            "status": RunStatus.RUNNING,
            "current": None,
            "context": next_step.context,
        }
    ]


def test_notify_rejects_empty_next_when_declared() -> None:
    store = _FakeStore()
    use_case = ExecuteNotifyStepUseCase(store=store)
    next_step = _build_next_step({"id": "start", "type": "notify", "message": "ok", "next": "   "})

    with pytest.raises(ValueError, match="requires non-empty next"):
        use_case.execute(next_step)
