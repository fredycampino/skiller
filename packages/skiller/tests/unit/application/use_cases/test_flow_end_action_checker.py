import pytest

from skiller.application.use_cases.flow.flow_end_action_checker import FlowEndActionChecker
from skiller.domain.flow.flow_raw_definition import FlowRawDefinition

pytestmark = pytest.mark.unit


def test_flow_end_action_checker_accepts_run_action() -> None:
    errors = []

    FlowEndActionChecker().check(
        flow=FlowRawDefinition(
            name="demo",
            start="build_args",
            steps=(),
            raw={
                "on_success": {
                    "action": {
                        "type": "run",
                        "label": "Open follow-up",
                        "arg": "--file ./flows/followup.yaml",
                        "params": '--result {{output_value("build_args").stdout}}',
                        "auto": True,
                    }
                }
            },
        ),
        errors=errors,
    )

    assert errors == []


def test_flow_end_action_checker_accepts_post_action() -> None:
    errors = []

    FlowEndActionChecker().check(
        flow=FlowRawDefinition(
            name="demo",
            start="build_args",
            steps=(),
            raw={
                "on_success": {
                    "action": {
                        "type": "post",
                        "label": "Auth success",
                        "arg": "load_session",
                        "params": "run_id={{inputs.continue_id}}",
                        "auto": True,
                    }
                }
            },
        ),
        errors=errors,
    )

    assert errors == []


def test_flow_end_action_checker_accepts_cleanup_without_action() -> None:
    errors = []

    FlowEndActionChecker().check(
        flow=FlowRawDefinition(
            name="demo",
            start="done",
            steps=(),
            raw={"on_success": {"cleanup": True}},
        ),
        errors=errors,
    )

    assert errors == []


def test_flow_end_action_checker_reports_invalid_action_fields() -> None:
    errors = []

    FlowEndActionChecker().check(
        flow=FlowRawDefinition(
            name="demo",
            start="done",
            steps=(),
            raw={
                "on_error": {
                    "action": {
                        "type": "open_url",
                        "label": "",
                        "arg": "",
                        "params": ["bad"],
                        "auto": "true",
                    }
                }
            },
        ),
        errors=errors,
    )

    assert [item.code for item in errors] == [
        "FLOW_END_ACTION_TYPE_UNSUPPORTED",
        "FLOW_END_ACTION_LABEL_MISSING",
        "FLOW_END_ACTION_ARG_MISSING",
        "FLOW_END_ACTION_PARAMS_INVALID",
        "FLOW_END_ACTION_AUTO_INVALID",
    ]


def test_flow_end_action_checker_reports_malformed_action_config() -> None:
    errors = []

    FlowEndActionChecker().check(
        flow=FlowRawDefinition(
            name="demo",
            start="done",
            steps=(),
            raw={"on_success": "bad", "on_error": {"action": "bad"}},
        ),
        errors=errors,
    )

    assert [item.code for item in errors] == [
        "FLOW_END_ACTION_INVALID",
        "FLOW_END_ACTION_ACTION_INVALID",
    ]


def test_flow_end_action_checker_reports_invalid_cleanup() -> None:
    errors = []

    FlowEndActionChecker().check(
        flow=FlowRawDefinition(
            name="demo",
            start="done",
            steps=(),
            raw={"on_success": {"cleanup": "true"}},
        ),
        errors=errors,
    )

    assert [item.code for item in errors] == ["FLOW_END_ACTION_CLEANUP_INVALID"]
