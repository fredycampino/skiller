import pytest

from skiller.application.use_cases.flow.flow_checker import FlowCheckerUseCase, FlowCheckStatus

pytestmark = pytest.mark.unit


class _FakeFlowRunner:
    def __init__(self, raw_flow: object) -> None:
        self.raw_flow = raw_flow
        self.calls: list[tuple[str, str]] = []

    def load(self, source: str, ref: str) -> object:
        self.calls.append((source, ref))
        return self.raw_flow


def test_flow_checker_accepts_valid_flow() -> None:
    use_case = FlowCheckerUseCase(
        runner=_FakeFlowRunner(
            {
                "name": "cloudflared",
                "start": "inspect_cloudflared",
                "steps": [
                    {
                        "shell": "inspect_cloudflared",
                        "command": "cloudflared tunnel list --output json",
                        "next": "summarize_tunnels",
                    },
                    {
                        "notify": "summarize_tunnels",
                        "message": '{{output_value("inspect_cloudflared").stderr}}',
                    },
                ],
            }
        )
    )
    result = use_case.execute("cloudflared", flow_source="internal")

    assert result.status == FlowCheckStatus.VALID
    assert result.errors == []


def test_flow_checker_reports_global_errors() -> None:
    use_case = FlowCheckerUseCase(runner=_FakeFlowRunner({}))
    result = use_case.execute("demo", flow_source="internal")

    assert result.status == FlowCheckStatus.INVALID
    assert [item.code for item in result.errors] == [
        "FLOW_NAME_MISSING",
        "FLOW_START_MISSING",
        "FLOW_STEPS_MISSING",
    ]


def test_flow_checker_rejects_steps_that_are_not_a_list() -> None:
    use_case = FlowCheckerUseCase(
        runner=_FakeFlowRunner(
            {
                "name": "cloudflared",
                "start": "show_message",
                "steps": {},
            }
        )
    )
    result = use_case.execute("demo", flow_source="internal")

    assert result.status == FlowCheckStatus.INVALID
    assert [item.code for item in result.errors] == ["FLOW_STEPS_INVALID"]


def test_flow_checker_rejects_direct_output_value_access() -> None:
    use_case = FlowCheckerUseCase(
        runner=_FakeFlowRunner(
            {
                "name": "demo",
                "start": "show_message",
                "steps": [
                    {"shell": "inspect", "command": "printf ok"},
                    {
                        "notify": "show_message",
                        "message": "{{step_executions.inspect.output.value.stdout}}",
                    },
                ],
            }
        )
    )
    result = use_case.execute("demo", flow_source="internal")

    assert result.status == FlowCheckStatus.INVALID
    assert [item.code for item in result.errors] == [
        "FLOW_OUTPUT_VALUE_DIRECT_OUTPUT_ACCESS"
    ]


def test_flow_checker_rejects_current_step_output_reference() -> None:
    use_case = FlowCheckerUseCase(
        runner=_FakeFlowRunner(
            {
                "name": "demo",
                "start": "show_message",
                "steps": [
                    {
                        "notify": "show_message",
                        "message": '{{output_value("show_message").message}}',
                    }
                ],
            }
        )
    )
    result = use_case.execute("demo", flow_source="internal")

    assert result.status == FlowCheckStatus.INVALID
    assert [item.code for item in result.errors] == ["FLOW_OUTPUT_VALUE_FORWARD_REFERENCE"]


def test_flow_checker_rejects_forward_output_value_reference() -> None:
    use_case = FlowCheckerUseCase(
        runner=_FakeFlowRunner(
            {
                "name": "demo",
                "start": "show_message",
                "steps": [
                    {
                        "notify": "show_message",
                        "message": '{{output_value("inspect").stdout}}',
                    },
                    {"shell": "inspect", "command": "printf ok"},
                ],
            }
        )
    )
    result = use_case.execute("demo", flow_source="internal")

    assert result.status == FlowCheckStatus.INVALID
    assert [item.code for item in result.errors] == ["FLOW_OUTPUT_VALUE_FORWARD_REFERENCE"]


def test_flow_checker_rejects_unknown_next_target() -> None:
    use_case = FlowCheckerUseCase(
        runner=_FakeFlowRunner(
            {
                "name": "demo",
                "start": "show_message",
                "steps": [
                    {
                        "notify": "show_message",
                        "message": "ok",
                        "next": "missing",
                    }
                ],
            }
        )
    )
    result = use_case.execute("demo", flow_source="internal")

    assert result.status == FlowCheckStatus.INVALID
    assert [item.code for item in result.errors] == ["FLOW_STEP_NEXT_NOT_FOUND"]


def test_flow_checker_rejects_unsupported_notify_format() -> None:
    use_case = FlowCheckerUseCase(
        runner=_FakeFlowRunner(
            {
                "name": "demo",
                "start": "show_message",
                "steps": [
                    {
                        "notify": "show_message",
                        "message": "ok",
                        "format": "html",
                    }
                ],
            }
        )
    )

    result = use_case.execute("demo", flow_source="internal")

    assert result.status == FlowCheckStatus.INVALID
    assert [item.code for item in result.errors] == [
        "FLOW_NOTIFY_FORMAT_UNSUPPORTED"
    ]


def test_flow_checker_accepts_notify_action() -> None:
    use_case = FlowCheckerUseCase(
        runner=_FakeFlowRunner(
            {
                "name": "demo",
                "start": "auth_link",
                "steps": [
                    {
                        "notify": "auth_link",
                        "message": "Authorize the app",
                        "action": {
                            "type": "open_url",
                            "label": "Open authorization",
                            "message": "Continue authorization in the browser.",
                            "url": "https://example.com/oauth/start",
                            "auto": True,
                        },
                    }
                ],
            }
        )
    )

    result = use_case.execute("demo", flow_source="internal")

    assert result.status == FlowCheckStatus.VALID
    assert result.errors == []


def test_flow_checker_accepts_notify_action_url_template() -> None:
    use_case = FlowCheckerUseCase(
        runner=_FakeFlowRunner(
            {
                "name": "demo",
                "start": "build_url",
                "steps": [
                    {
                        "shell": "build_url",
                        "command": "printf https://example.com/oauth/start",
                        "next": "auth_link",
                    },
                    {
                        "notify": "auth_link",
                        "message": "Authorize the app",
                        "action": {
                            "type": "open_url",
                            "label": "Open authorization",
                            "url": '{{output_value("build_url").stdout}}',
                        },
                    },
                ],
            }
        )
    )

    result = use_case.execute("demo", flow_source="internal")

    assert result.status == FlowCheckStatus.VALID
    assert result.errors == []


def test_flow_checker_rejects_notify_action_with_invalid_auto() -> None:
    use_case = FlowCheckerUseCase(
        runner=_FakeFlowRunner(
            {
                "name": "demo",
                "start": "auth_link",
                "steps": [
                    {
                        "notify": "auth_link",
                        "message": "Authorize the app",
                        "action": {
                            "type": "open_url",
                            "label": "Open authorization",
                            "url": "https://example.com/oauth/start",
                            "auto": "false",
                        },
                    }
                ],
            }
        )
    )

    result = use_case.execute("demo", flow_source="internal")

    assert result.status == FlowCheckStatus.INVALID
    assert [item.code for item in result.errors] == [
        "FLOW_NOTIFY_ACTION_AUTO_INVALID"
    ]


def test_flow_checker_rejects_notify_action_with_invalid_message() -> None:
    use_case = FlowCheckerUseCase(
        runner=_FakeFlowRunner(
            {
                "name": "demo",
                "start": "auth_link",
                "steps": [
                    {
                        "notify": "auth_link",
                        "message": "Authorize the app",
                        "action": {
                            "type": "open_url",
                            "label": "Open authorization",
                            "message": ["invalid"],
                            "url": "https://example.com/oauth/start",
                        },
                    }
                ],
            }
        )
    )

    result = use_case.execute("demo", flow_source="internal")

    assert result.status == FlowCheckStatus.INVALID
    assert [item.code for item in result.errors] == [
        "FLOW_NOTIFY_ACTION_MESSAGE_INVALID"
    ]


def test_flow_checker_rejects_notify_action_with_unsupported_url() -> None:
    use_case = FlowCheckerUseCase(
        runner=_FakeFlowRunner(
            {
                "name": "demo",
                "start": "auth_link",
                "steps": [
                    {
                        "notify": "auth_link",
                        "message": "Authorize the app",
                        "action": {
                            "type": "open_url",
                            "label": "Open authorization",
                            "url": "mailto:test@example.com",
                        },
                    }
                ],
            }
        )
    )

    result = use_case.execute("demo", flow_source="internal")

    assert result.status == FlowCheckStatus.INVALID
    assert [item.code for item in result.errors] == [
        "FLOW_NOTIFY_ACTION_URL_UNSUPPORTED"
    ]


def test_flow_checker_rejects_unsupported_helper() -> None:
    use_case = FlowCheckerUseCase(
        runner=_FakeFlowRunner(
            {
                "name": "demo",
                "start": "show_message",
                "steps": [
                    {"shell": "inspect", "command": "printf ok"},
                    {
                        "notify": "show_message",
                        "message": '{{output("inspect").stdout}}',
                    },
                ],
            }
        )
    )
    result = use_case.execute("demo", flow_source="internal")

    assert result.status == FlowCheckStatus.INVALID
    assert [item.code for item in result.errors] == [
        "FLOW_OUTPUT_VALUE_UNSUPPORTED_HELPER"
    ]


def test_flow_checker_rejects_non_object_payload() -> None:
    use_case = FlowCheckerUseCase(runner=_FakeFlowRunner(["bad"]))
    result = use_case.execute("demo", flow_source="internal")

    assert result.status == FlowCheckStatus.INVALID
    assert [item.code for item in result.errors] == ["FLOW_FORMAT_INVALID"]


def test_flow_checker_rejects_send_step_without_required_fields() -> None:
    use_case = FlowCheckerUseCase(
        runner=_FakeFlowRunner(
            {
                "name": "demo",
                "start": "reply",
                "steps": [{"send": "reply"}],
            }
        )
    )

    result = use_case.execute("demo", flow_source="internal")

    assert result.status == FlowCheckStatus.INVALID
    assert [item.code for item in result.errors] == [
        "FLOW_SEND_CHANNEL_MISSING",
        "FLOW_SEND_KEY_MISSING",
        "FLOW_SEND_MESSAGE_MISSING",
    ]


def test_flow_checker_rejects_send_step_with_unsupported_channel() -> None:
    use_case = FlowCheckerUseCase(
        runner=_FakeFlowRunner(
            {
                "name": "demo",
                "start": "reply",
                "steps": [
                    {
                        "send": "reply",
                        "channel": "telegram",
                        "key": "chat-1",
                        "message": "hola",
                    }
                ],
            }
        )
    )

    result = use_case.execute("demo", flow_source="internal")

    assert result.status == FlowCheckStatus.INVALID
    assert [item.code for item in result.errors] == ["FLOW_SEND_CHANNEL_UNSUPPORTED"]
