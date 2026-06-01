import pytest

from skiller.application.use_cases.flow.flow_shape_checker import FlowShapeChecker
from skiller.domain.flow.flow_raw_definition import FlowRawDefinition, FlowRawStepDefinition

pytestmark = pytest.mark.unit


def test_flow_shape_checker_rejects_non_object_flow() -> None:
    errors = []

    result = FlowShapeChecker().check(
        flow=FlowRawDefinition(name=None, start=None, steps=None, raw=[]),
        errors=errors,
    )

    assert not result.can_continue
    assert [item.code for item in errors] == ["FLOW_FORMAT_INVALID"]


def test_flow_shape_checker_reports_missing_global_fields() -> None:
    errors = []

    result = FlowShapeChecker().check(
        flow=FlowRawDefinition(name=None, start=None, steps=None, raw={}),
        errors=errors,
    )

    assert not result.can_continue
    assert [item.code for item in errors] == [
        "FLOW_NAME_MISSING",
        "FLOW_START_MISSING",
        "FLOW_STEPS_MISSING",
    ]


def test_flow_shape_checker_rejects_non_list_steps() -> None:
    errors = []

    result = FlowShapeChecker().check(
        flow=FlowRawDefinition(name="demo", start="hello", steps=None, raw={"steps": {}}),
        errors=errors,
    )

    assert not result.can_continue
    assert [item.code for item in errors] == ["FLOW_STEPS_INVALID"]


def test_flow_shape_checker_accepts_shape_with_steps() -> None:
    errors = []
    raw_step = FlowRawStepDefinition(
        index=0,
        step_id="hello",
        step_type="notify",
        body={"message": "Hello"},
        raw={"notify": "hello", "message": "Hello"},
    )

    result = FlowShapeChecker().check(
        flow=FlowRawDefinition(
            name="demo",
            start="hello",
            steps=(raw_step,),
            raw={"name": "demo", "start": "hello", "steps": []},
        ),
        errors=errors,
    )

    assert result.can_continue
    assert result.start == "hello"
    assert result.steps == (raw_step,)
    assert errors == []
