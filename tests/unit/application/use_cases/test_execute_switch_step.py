import pytest

from skiller.application.use_cases.execute.execute_switch_step import ExecuteSwitchStepUseCase
from skiller.application.use_cases.render.render_current_step import CurrentStep, StepType
from skiller.application.use_cases.shared.step_execution_result import StepExecutionStatus
from skiller.domain.run_context_model import RunContext
from skiller.domain.run_model import RunStatus
from skiller.domain.step_execution_model import SwitchOutput

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


def _build_current_step(
    *,
    value: object = "retry",
    cases: object = None,
    default: object = "unknown_action",
) -> CurrentStep:
    step: dict[str, object] = {
        "value": value,
        "cases": cases
        if cases is not None
        else {"retry": "retry_notice", "ask_human": "human_notice"},
        "default": default,
    }
    return CurrentStep(
        run_id="run-1",
        step_index=1,
        step_id="decide_action",
        step_type=StepType.SWITCH,
        step=step,
        context=RunContext(inputs={}, step_executions={}),
    )


def test_switch_step_moves_current_to_matching_case() -> None:
    store = _FakeStore()
    use_case = ExecuteSwitchStepUseCase(store=store)
    current_step = _build_current_step()

    result = use_case.execute(current_step)

    assert result.status == StepExecutionStatus.NEXT
    assert result.next_step_id == "retry_notice"
    assert result.execution is not None
    assert result.execution.output == SwitchOutput(
        text="Route selected: retry_notice.",
        next_step_id="retry_notice",
    )
    assert current_step.context.step_executions["decide_action"] == result.execution
    assert store.updated_runs == [
        {
            "run_id": "run-1",
            "status": RunStatus.RUNNING,
            "current": "retry_notice",
            "context": current_step.context,
        }
    ]
    assert store.events == []


def test_switch_step_falls_back_to_default_when_no_case_matches() -> None:
    store = _FakeStore()
    use_case = ExecuteSwitchStepUseCase(store=store)
    current_step = _build_current_step(value="done")

    result = use_case.execute(current_step)

    assert result.status == StepExecutionStatus.NEXT
    assert result.next_step_id == "unknown_action"
    assert result.execution is not None
    assert result.execution.output == SwitchOutput(
        text="Route selected: unknown_action.",
        next_step_id="unknown_action",
    )
    assert current_step.context.step_executions["decide_action"] == result.execution


@pytest.mark.parametrize(
    ("field", "step_kwargs", "expected_message"),
    [
        ("value", {"value": None}, None),
        ("missing_value", {}, "requires value"),
        ("cases_shape", {"cases": []}, "requires cases object"),
        ("cases_empty", {"cases": {}}, "requires non-empty cases object"),
        ("default_missing", {"default": None}, "requires default"),
        ("case_target_empty", {"cases": {"retry": "   "}}, "requires non-empty cases target"),
        (
            "default_target_empty",
            {"value": "done", "default": "   "},
            "requires non-empty default target",
        ),
    ],
)
def test_switch_step_validates_contract(
    field: str, step_kwargs: dict[str, object], expected_message: str | None
) -> None:
    _ = field
    if expected_message is None:
        store = _FakeStore()
        use_case = ExecuteSwitchStepUseCase(store=store)
        current_step = _build_current_step(**step_kwargs)

        result = use_case.execute(current_step)

        assert result.next_step_id == "unknown_action"
        assert result.execution is not None
        assert result.execution.output == SwitchOutput(
            text="Route selected: unknown_action.",
            next_step_id="unknown_action",
        )
        assert current_step.context.step_executions["decide_action"] == result.execution
        return

    step = {
        "cases": {"retry": "retry_notice"},
        "default": "unknown_action",
    }
    if field != "missing_value":
        step["value"] = "retry"
    step.update(step_kwargs)

    current_step = CurrentStep(
        run_id="run-1",
        step_index=1,
        step_id="decide_action",
        step_type=StepType.SWITCH,
        step=step,
        context=RunContext(inputs={}, step_executions={}),
    )
    store = _FakeStore()
    use_case = ExecuteSwitchStepUseCase(store=store)

    with pytest.raises(ValueError, match=expected_message):
        use_case.execute(current_step)
