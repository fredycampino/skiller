import pytest

from skiller.application.use_cases.flow.flow_check_model import ParsedFlowStep
from skiller.application.use_cases.flow.flow_step_fields_checker import FlowStepFieldsChecker

pytestmark = pytest.mark.unit


def test_flow_step_fields_checker_reports_send_required_fields_and_channel() -> None:
    errors = []

    FlowStepFieldsChecker().check(
        steps=[
            ParsedFlowStep(
                index=0,
                step_id="reply",
                step_type="send",
                body={"channel": "telegram"},
            )
        ],
        errors=errors,
    )

    assert [item.code for item in errors] == [
        "FLOW_SEND_KEY_MISSING",
        "FLOW_SEND_MESSAGE_MISSING",
        "FLOW_SEND_CHANNEL_UNSUPPORTED",
    ]


def test_flow_step_fields_checker_reports_notify_format() -> None:
    errors = []

    FlowStepFieldsChecker().check(
        steps=[
            ParsedFlowStep(
                index=0,
                step_id="hello",
                step_type="notify",
                body={"message": "Hello", "format": "html"},
            )
        ],
        errors=errors,
    )

    assert [item.code for item in errors] == ["FLOW_NOTIFY_FORMAT_UNSUPPORTED"]


def test_flow_step_fields_checker_delegates_notify_action_validation() -> None:
    errors = []

    FlowStepFieldsChecker().check(
        steps=[
            ParsedFlowStep(
                index=0,
                step_id="auth_link",
                step_type="notify",
                body={
                    "message": "Authorize",
                    "action": {
                        "type": "open_url",
                        "label": "Open",
                        "url": "https://example.com",
                        "auto": "true",
                    },
                },
            )
        ],
        errors=errors,
    )

    assert [item.code for item in errors] == ["FLOW_NOTIFY_ACTION_AUTO_INVALID"]


def test_flow_step_fields_checker_reports_agent_wait_and_mcp_required_fields() -> None:
    errors = []

    FlowStepFieldsChecker().check(
        steps=[
            ParsedFlowStep(index=0, step_id="agent", step_type="agent", body={}),
            ParsedFlowStep(
                index=1,
                step_id="wait_webhook",
                step_type="wait_webhook",
                body={"webhook": "auth"},
            ),
            ParsedFlowStep(
                index=2,
                step_id="wait_channel",
                step_type="wait_channel",
                body={"channel": "whatsapp"},
            ),
            ParsedFlowStep(index=3, step_id="mcp", step_type="mcp", body={"server": "local"}),
        ],
        errors=errors,
    )

    assert [item.code for item in errors] == [
        "FLOW_AGENT_SYSTEM_MISSING",
        "FLOW_AGENT_TASK_MISSING",
        "FLOW_WAIT_WEBHOOK_KEY_MISSING",
        "FLOW_WAIT_CHANNEL_KEY_MISSING",
        "FLOW_MCP_TOOL_MISSING",
    ]
