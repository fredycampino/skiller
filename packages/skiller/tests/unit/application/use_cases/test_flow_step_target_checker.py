import pytest

from skiller.application.use_cases.flow.flow_check_model import ParsedFlowStep
from skiller.application.use_cases.flow.flow_step_target_checker import FlowStepTargetChecker

pytestmark = pytest.mark.unit


def test_flow_step_target_checker_reports_unknown_start_and_next() -> None:
    errors = []
    checker = FlowStepTargetChecker()

    checker.check_start(start="missing_start", step_ids={"hello"}, errors=errors)
    checker.check_steps(
        steps=[
            ParsedFlowStep(
                index=0,
                step_id="hello",
                step_type="notify",
                body={"next": "missing_next"},
            )
        ],
        step_ids={"hello"},
        errors=errors,
    )

    assert [item.code for item in errors] == [
        "FLOW_START_STEP_NOT_FOUND",
        "FLOW_STEP_NEXT_NOT_FOUND",
    ]


def test_flow_step_target_checker_reports_switch_and_when_targets() -> None:
    errors = []

    FlowStepTargetChecker().check_steps(
        steps=[
            ParsedFlowStep(
                index=0,
                step_id="switch_step",
                step_type="switch",
                body={"cases": {"ok": "missing_case"}, "default": "missing_default"},
            ),
            ParsedFlowStep(
                index=1,
                step_id="when_step",
                step_type="when",
                body={
                    "branches": [{"then": "missing_branch"}],
                    "default": "missing_when_default",
                },
            ),
        ],
        step_ids={"switch_step", "when_step"},
        errors=errors,
    )

    assert [item.code for item in errors] == [
        "FLOW_SWITCH_CASE_TARGET_NOT_FOUND",
        "FLOW_SWITCH_DEFAULT_TARGET_NOT_FOUND",
        "FLOW_WHEN_BRANCH_TARGET_NOT_FOUND",
        "FLOW_WHEN_DEFAULT_TARGET_NOT_FOUND",
    ]
