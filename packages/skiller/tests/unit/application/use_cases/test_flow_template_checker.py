import pytest

from skiller.application.use_cases.flow.flow_check_model import ParsedFlowStep
from skiller.application.use_cases.flow.flow_template_checker import FlowTemplateChecker
from skiller.domain.flow.flow_raw_definition import FlowRawDefinition

pytestmark = pytest.mark.unit


def test_flow_template_checker_reports_direct_output_value_access() -> None:
    errors = []

    FlowTemplateChecker().check_steps(
        steps=[
            ParsedFlowStep(
                index=0,
                step_id="show_message",
                step_type="notify",
                body={"message": "{{step_executions.inspect.output.value.stdout}}"},
            )
        ],
        step_ids={"show_message"},
        errors=errors,
    )

    assert [item.code for item in errors] == ["FLOW_OUTPUT_VALUE_DIRECT_OUTPUT_ACCESS"]


def test_flow_template_checker_reports_forward_output_value_reference() -> None:
    errors = []

    FlowTemplateChecker().check_steps(
        steps=[
            ParsedFlowStep(
                index=0,
                step_id="show_message",
                step_type="notify",
                body={"message": '{{output_value("inspect").stdout}}'},
            ),
            ParsedFlowStep(
                index=1,
                step_id="inspect",
                step_type="shell",
                body={"command": "printf ok"},
            ),
        ],
        step_ids={"show_message", "inspect"},
        errors=errors,
    )

    assert [item.code for item in errors] == ["FLOW_OUTPUT_VALUE_FORWARD_REFERENCE"]


def test_flow_template_checker_reports_unsupported_helper() -> None:
    errors = []

    FlowTemplateChecker().check_steps(
        steps=[
            ParsedFlowStep(
                index=0,
                step_id="show_message",
                step_type="notify",
                body={"message": '{{output("inspect").stdout}}'},
            )
        ],
        step_ids={"show_message"},
        errors=errors,
    )

    assert [item.code for item in errors] == ["FLOW_OUTPUT_VALUE_UNSUPPORTED_HELPER"]


def test_flow_template_checker_checks_end_action_templates() -> None:
    errors = []

    FlowTemplateChecker().check_end_actions(
        flow=FlowRawDefinition(
            name="demo",
            start="show_message",
            steps=(),
            raw={
                "on_success": {
                    "action": {
                        "type": "run",
                        "label": "Next",
                        "arg": "--file next.yaml",
                        "params": '--value {{output_value("show_message").stdout}}',
                    }
                }
            },
        ),
        steps=[
            ParsedFlowStep(
                index=0,
                step_id="show_message",
                step_type="notify",
                body={"message": "ok"},
            )
        ],
        step_ids={"show_message"},
        errors=errors,
    )

    assert errors == []
