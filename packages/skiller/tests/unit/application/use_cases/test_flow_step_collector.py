import pytest

from skiller.application.use_cases.flow.flow_step_collector import FlowStepCollector
from skiller.domain.flow.flow_raw_definition import FlowRawStepDefinition

pytestmark = pytest.mark.unit


def test_flow_step_collector_collects_valid_steps() -> None:
    errors = []

    steps = FlowStepCollector().collect(
        raw_steps=(
            FlowRawStepDefinition(
                index=0,
                step_id="hello",
                step_type="notify",
                body={"message": "Hello"},
                raw={"notify": "hello", "message": "Hello"},
            ),
        ),
        errors=errors,
    )

    assert errors == []
    assert len(steps) == 1
    assert steps[0].step_id == "hello"
    assert steps[0].step_type == "notify"
    assert steps[0].body == {"message": "Hello"}


def test_flow_step_collector_reports_primary_header_errors() -> None:
    errors = []

    steps = FlowStepCollector().collect(
        raw_steps=(
            FlowRawStepDefinition(index=0, step_id=None, step_type=None, body=None, raw="bad"),
            FlowRawStepDefinition(index=1, step_id=None, step_type=None, body={}, raw={}),
            FlowRawStepDefinition(
                index=2,
                step_id=None,
                step_type="unknown",
                body={},
                raw={"unknown": "x"},
            ),
            FlowRawStepDefinition(
                index=3,
                step_id=None,
                step_type="notify",
                body={},
                raw={"notify": "a", "shell": "b"},
            ),
        ),
        errors=errors,
    )

    assert steps == []
    assert [item.code for item in errors] == [
        "FLOW_STEP_PRIMARY_HEADER_MISSING",
        "FLOW_STEP_PRIMARY_HEADER_MISSING",
        "FLOW_STEP_PRIMARY_HEADER_INVALID",
        "FLOW_STEP_PRIMARY_HEADER_INVALID",
    ]


def test_flow_step_collector_reports_missing_and_duplicate_step_ids() -> None:
    errors = []

    steps = FlowStepCollector().collect(
        raw_steps=(
            FlowRawStepDefinition(
                index=0,
                step_id=None,
                step_type="notify",
                body={},
                raw={"notify": ""},
            ),
            FlowRawStepDefinition(
                index=1,
                step_id="same",
                step_type="notify",
                body={},
                raw={"notify": "same", "message": "one"},
            ),
            FlowRawStepDefinition(
                index=2,
                step_id="same",
                step_type="notify",
                body={},
                raw={"notify": "same", "message": "two"},
            ),
        ),
        errors=errors,
    )

    assert [item.step_id for item in steps] == ["same"]
    assert [item.code for item in errors] == [
        "FLOW_STEP_ID_MISSING",
        "FLOW_STEP_ID_DUPLICATED",
    ]
