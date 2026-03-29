import pytest

from skiller.application.use_cases.execute_assign_step import ExecuteAssignStepUseCase
from skiller.application.use_cases.render_current_step import CurrentStep, StepType
from skiller.application.use_cases.step_execution_result import StepExecutionStatus
from skiller.domain.run_context_model import RunContext
from skiller.domain.run_model import RunStatus
from skiller.domain.step_execution_model import AssignOutput

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


def _build_current_step(values: object, *, next_step_id: object = "done") -> CurrentStep:
    step: dict[str, object] = {"values": values}
    if next_step_id is not None:
        step["next"] = next_step_id

    return CurrentStep(
        run_id="run-1",
        step_index=1,
        step_id="prepare",
        step_type=StepType.ASSIGN,
        step=step,
        context=RunContext(
            inputs={"issue": "boom"}, step_executions={}
        ),
    )


def test_assign_step_persists_values_and_moves_current_to_explicit_next() -> None:
    store = _FakeStore()
    use_case = ExecuteAssignStepUseCase(store=store)
    current_step = _build_current_step(
        {
            "action": "retry",
            "summary": "boom",
            "meta": {"source": "assign"},
            "tags": ["triage", "retry"],
        }
    )

    result = use_case.execute(current_step)

    assert result.status == StepExecutionStatus.NEXT
    assert result.next_step_id == "done"
    assert result.execution is not None
    assert result.execution.output == AssignOutput(
        text="Values assigned.",
        assigned={
            "action": "retry",
            "summary": "boom",
            "meta": {"source": "assign"},
            "tags": ["triage", "retry"],
        },
    )
    assert current_step.context.step_executions["prepare"] == result.execution
    assert store.updated_runs == [
        {
            "run_id": "run-1",
            "status": RunStatus.RUNNING,
            "current": "done",
            "context": current_step.context,
        }
    ]
    assert store.events == []


def test_assign_step_marks_completed_when_next_is_missing() -> None:
    store = _FakeStore()
    use_case = ExecuteAssignStepUseCase(store=store)
    current_step = _build_current_step({"action": "retry"}, next_step_id=None)

    result = use_case.execute(current_step)

    assert result.status == StepExecutionStatus.COMPLETED
    assert result.next_step_id is None
    assert result.execution is not None
    assert result.execution.output == AssignOutput(
        text="Values assigned.",
        assigned={"action": "retry"},
    )
    assert store.updated_runs == [
        {
            "run_id": "run-1",
            "status": RunStatus.RUNNING,
            "current": None,
            "context": current_step.context,
        }
    ]


def test_assign_step_rejects_empty_next_when_declared() -> None:
    store = _FakeStore()
    use_case = ExecuteAssignStepUseCase(store=store)
    current_step = _build_current_step({"action": "retry"}, next_step_id="   ")

    with pytest.raises(ValueError, match="requires non-empty next"):
        use_case.execute(current_step)


@pytest.mark.parametrize("values", [None, [], "retry", {}])
def test_assign_step_requires_non_empty_values_object(values: object) -> None:
    store = _FakeStore()
    use_case = ExecuteAssignStepUseCase(store=store)
    current_step = _build_current_step(values)

    expected_message = "requires values object"
    if values == {}:
        expected_message = "requires non-empty values object"

    with pytest.raises(ValueError, match=expected_message):
        use_case.execute(current_step)
