import pytest

from skiller.application.use_cases.flow.flow_check_model import ParsedFlowStep
from skiller.application.use_cases.flow.flow_notify_action_checker import FlowNotifyActionChecker

pytestmark = pytest.mark.unit


def test_flow_notify_action_checker_accepts_open_url_action() -> None:
    errors = []

    FlowNotifyActionChecker().check(
        step=ParsedFlowStep(
            index=0,
            step_id="auth_link",
            step_type="notify",
            body={
                "action": {
                    "type": "open_url",
                    "label": "Open authorization",
                    "message": "Continue in browser.",
                    "url": "https://example.com/oauth/start",
                    "auto": True,
                }
            },
        ),
        errors=errors,
    )

    assert errors == []


def test_flow_notify_action_checker_reports_non_object_action() -> None:
    errors = []

    FlowNotifyActionChecker().check(
        step=ParsedFlowStep(
            index=0,
            step_id="auth_link",
            step_type="notify",
            body={"action": "bad"},
        ),
        errors=errors,
    )

    assert [item.code for item in errors] == ["FLOW_NOTIFY_ACTION_INVALID"]


def test_flow_notify_action_checker_reports_invalid_action_fields() -> None:
    errors = []

    FlowNotifyActionChecker().check(
        step=ParsedFlowStep(
            index=0,
            step_id="auth_link",
            step_type="notify",
            body={
                "action": {
                    "type": "run",
                    "label": "",
                    "message": ["bad"],
                    "url": "mailto:test@example.com",
                    "auto": "true",
                }
            },
        ),
        errors=errors,
    )

    assert [item.code for item in errors] == [
        "FLOW_NOTIFY_ACTION_TYPE_UNSUPPORTED",
        "FLOW_NOTIFY_ACTION_LABEL_MISSING",
        "FLOW_NOTIFY_ACTION_MESSAGE_INVALID",
        "FLOW_NOTIFY_ACTION_URL_UNSUPPORTED",
        "FLOW_NOTIFY_ACTION_AUTO_INVALID",
    ]
