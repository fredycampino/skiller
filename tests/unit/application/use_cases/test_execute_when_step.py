import pytest

from skiller.application.use_cases.execute_when_step import ExecuteWhenStepUseCase
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


def _build_current_step(
    *,
    value: object = 85,
    branches: object = None,
    default: object = "fail",
) -> CurrentStep:
    step: dict[str, object] = {
        "id": "decide_score",
        "type": "when",
        "value": value,
        "branches": branches
        if branches is not None
        else [
            {"gt": 90, "then": "excellent"},
            {"gt": 70, "then": "good"},
        ],
        "default": default,
    }
    return CurrentStep(
        run_id="run-1",
        step_index=1,
        step_id="decide_score",
        step_type=StepType.WHEN,
        step=step,
        context=RunContext(inputs={}, results={}),
    )


def test_when_step_moves_current_to_first_matching_branch() -> None:
    store = _FakeStore()
    use_case = ExecuteWhenStepUseCase(store=store)
    current_step = _build_current_step(value=85)

    result = use_case.execute(current_step)

    assert result.status == StepExecutionStatus.NEXT
    assert result.next_step_id == "good"
    assert current_step.context.results["decide_score"] == {
        "value": 85,
        "next": "good",
    }
    assert store.updated_runs == [
        {
            "run_id": "run-1",
            "status": RunStatus.RUNNING,
            "current": "good",
            "context": current_step.context,
        }
    ]
    assert store.events == [
        {
            "type": "WHEN_DECISION",
            "payload": {
                "step": "decide_score",
                "value": 85,
                "next": "good",
                "branch": 1,
                "op": "gt",
                "right": 70,
            },
            "run_id": "run-1",
        }
    ]


def test_when_step_supports_single_branch_as_binary_if() -> None:
    store = _FakeStore()
    use_case = ExecuteWhenStepUseCase(store=store)
    current_step = _build_current_step(
        value="retry",
        branches=[{"eq": "retry", "then": "retry_notice"}],
        default="human_notice",
    )

    result = use_case.execute(current_step)

    assert result.status == StepExecutionStatus.NEXT
    assert result.next_step_id == "retry_notice"
    assert current_step.context.results["decide_score"] == {
        "value": "retry",
        "next": "retry_notice",
    }


def test_when_step_falls_back_to_default_when_no_branch_matches() -> None:
    store = _FakeStore()
    use_case = ExecuteWhenStepUseCase(store=store)
    current_step = _build_current_step(value=40)

    result = use_case.execute(current_step)

    assert result.status == StepExecutionStatus.NEXT
    assert result.next_step_id == "fail"
    assert current_step.context.results["decide_score"] == {
        "value": 40,
        "next": "fail",
    }
    assert store.events == [
        {
            "type": "WHEN_DECISION",
            "payload": {
                "step": "decide_score",
                "value": 40,
                "next": "fail",
                "branch": None,
                "op": None,
                "right": None,
            },
            "run_id": "run-1",
        }
    ]


@pytest.mark.parametrize(
    ("label", "step_kwargs", "expected_message"),
    [
        ("missing_value", {"omit_value": True}, "requires value"),
        ("branches_shape", {"branches": {}}, "requires branches list"),
        ("branches_empty", {"branches": []}, "requires non-empty branches list"),
        ("default_missing", {"default": None}, "requires default"),
        ("branch_shape", {"branches": ["bad"]}, "requires branch 0 object"),
        ("branch_missing_then", {"branches": [{"gt": 90}]}, "requires branch 0 then"),
        (
            "branch_empty_then",
            {"branches": [{"gt": 90, "then": "   "}]},
            "requires non-empty branch 0 then",
        ),
        (
            "branch_no_op",
            {"branches": [{"then": "good"}]},
            "requires exactly one operator in branch 0",
        ),
        (
            "branch_two_ops",
            {"branches": [{"gt": 90, "lt": 100, "then": "good"}]},
            "requires exactly one operator in branch 0",
        ),
        (
            "branch_bad_op",
            {"branches": [{"contains": 90, "then": "good"}]},
            "uses unsupported when operator",
        ),
        (
            "numeric_left_invalid",
            {"value": "85", "branches": [{"gt": 70, "then": "good"}]},
            "requires numeric operands for operator 'gt'",
        ),
        (
            "numeric_right_invalid",
            {"value": 85, "branches": [{"gt": "70", "then": "good"}]},
            "requires numeric operands for operator 'gt'",
        ),
    ],
)
def test_when_step_validates_contract(
    label: str, step_kwargs: dict[str, object], expected_message: str
) -> None:
    _ = label
    step: dict[str, object] = {
        "id": "decide_score",
        "type": "when",
        "branches": [{"gt": 90, "then": "excellent"}],
        "default": "fail",
    }
    if not bool(step_kwargs.get("omit_value")):
        step["value"] = 85

    step_kwargs = {key: value for key, value in step_kwargs.items() if key != "omit_value"}
    step.update(step_kwargs)

    current_step = CurrentStep(
        run_id="run-1",
        step_index=1,
        step_id="decide_score",
        step_type=StepType.WHEN,
        step=step,
        context=RunContext(inputs={}, results={}),
    )
    store = _FakeStore()
    use_case = ExecuteWhenStepUseCase(store=store)

    with pytest.raises(ValueError, match=expected_message):
        use_case.execute(current_step)
