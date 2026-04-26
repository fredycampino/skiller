import pytest

from skiller.application.use_cases.execute.execute_notify_step import ExecuteNotifyStepUseCase
from skiller.application.use_cases.render.render_current_step import CurrentStep, StepType
from skiller.application.use_cases.shared.step_execution_result import StepExecutionStatus
from skiller.domain.run_context_model import RunContext
from skiller.domain.run_model import RunStatus
from skiller.domain.step_execution_model import NotifyOutput

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
        step_id="show_message",
        step_type=StepType.NOTIFY,
        step=step,
        context=RunContext(inputs={}, step_executions={}),
    )


def test_notify_moves_current_to_explicit_next() -> None:
    store = _FakeStore()
    use_case = ExecuteNotifyStepUseCase(store=store)
    next_step = _build_next_step({"message": "ok", "next": "done"})

    result = use_case.execute(next_step)

    assert result.status == StepExecutionStatus.NEXT
    assert result.next_step_id == "done"
    assert result.execution is not None
    assert result.execution.output == NotifyOutput(text="ok", message="ok")
    assert next_step.context.step_executions["show_message"] == result.execution
    assert store.updated_runs == [
        {
            "run_id": "run-1",
            "status": RunStatus.RUNNING,
            "current": "done",
            "context": next_step.context,
        }
    ]
    assert store.events == []


def test_notify_marks_completed_when_next_is_missing() -> None:
    store = _FakeStore()
    use_case = ExecuteNotifyStepUseCase(store=store)
    next_step = _build_next_step({"message": "ok"})

    result = use_case.execute(next_step)

    assert result.status == StepExecutionStatus.COMPLETED
    assert result.next_step_id is None
    assert result.execution is not None
    assert result.execution.output == NotifyOutput(text="ok", message="ok")
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
    next_step = _build_next_step({"message": "ok", "next": "   "})

    with pytest.raises(ValueError, match="requires non-empty next"):
        use_case.execute(next_step)
