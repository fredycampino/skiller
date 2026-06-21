import pytest

from skiller.application.use_cases.flow.flow_readiness_checker import (
    FlowReadinessCheckError,
    FlowReadinessCheckerUseCase,
    FlowReadinessCheckStatus,
)

pytestmark = pytest.mark.unit


class _FakeFlowRunner:
    def __init__(self, flow: object) -> None:
        self.flow = flow
        self.calls: list[dict[str, str]] = []

    def load(self, source: str, ref: str) -> object:
        self.calls.append({"flow_source": source, "flow_ref": ref})
        return self.flow


class _FakeServerStatus:
    def __init__(self, *, available: bool) -> None:
        self.available = available
        self.calls = 0

    def is_available(self) -> bool:
        self.calls += 1
        return self.available


class _FakeChannelSender:
    def __init__(self, *, available: bool) -> None:
        self.available = available
        self.calls: list[str] = []

    def is_available(self, *, channel: str) -> bool:
        self.calls.append(channel)
        return self.available


def test_returns_valid_when_flow_does_not_use_server_steps() -> None:
    server_status = _FakeServerStatus(available=False)
    channel_sender = _FakeChannelSender(available=False)
    use_case = FlowReadinessCheckerUseCase(
        runner=_FakeFlowRunner(
            {
                "name": "notify_test",
                "start": "show_message",
                "steps": [
                    {"notify": "show_message", "message": "ok"},
                ],
            }
        ),
        server_status=server_status,
        channel_sender=channel_sender,
    )

    result = use_case.execute("notify_test", flow_source="internal")

    assert result.status == FlowReadinessCheckStatus.VALID
    assert result.errors == []
    assert server_status.calls == 0
    assert channel_sender.calls == []


def test_returns_valid_when_wait_channel_flow_has_server_available() -> None:
    server_status = _FakeServerStatus(available=True)
    channel_sender = _FakeChannelSender(available=True)
    use_case = FlowReadinessCheckerUseCase(
        runner=_FakeFlowRunner(
            {
                "name": "whatsapp_demo",
                "start": "listen_whatsapp",
                "steps": [
                    {
                        "wait_channel": "listen_whatsapp",
                        "channel": "whatsapp",
                        "key": "all",
                    }
                ],
            }
        ),
        server_status=server_status,
        channel_sender=channel_sender,
    )

    result = use_case.execute("whatsapp_demo", flow_source="internal")

    assert result.status == FlowReadinessCheckStatus.VALID
    assert result.errors == []
    assert server_status.calls == 1
    assert channel_sender.calls == ["whatsapp"]


def test_returns_invalid_when_wait_channel_flow_has_server_unavailable() -> None:
    server_status = _FakeServerStatus(available=False)
    channel_sender = _FakeChannelSender(available=True)
    use_case = FlowReadinessCheckerUseCase(
        runner=_FakeFlowRunner(
            {
                "name": "whatsapp_demo",
                "start": "listen_whatsapp",
                "steps": [
                    {
                        "wait_channel": "listen_whatsapp",
                        "channel": "whatsapp",
                        "key": "all",
                    }
                ],
            }
        ),
        server_status=server_status,
        channel_sender=channel_sender,
    )

    result = use_case.execute("whatsapp_demo", flow_source="internal")

    assert result.status == FlowReadinessCheckStatus.INVALID
    assert result.errors == [
        FlowReadinessCheckError(
            code="FLOW_SERVER_UNAVAILABLE",
            message=(
                "FLOW_SERVER_UNAVAILABLE: flow requires local server for wait_channel "
                "(step=listen_whatsapp)"
            ),
        )
    ]
    assert server_status.calls == 1
    assert channel_sender.calls == []


def test_returns_valid_when_wait_webhook_flow_has_server_available() -> None:
    server_status = _FakeServerStatus(available=True)
    channel_sender = _FakeChannelSender(available=False)
    use_case = FlowReadinessCheckerUseCase(
        runner=_FakeFlowRunner(
            {
                "name": "webhook_demo",
                "start": "listen_webhook",
                "steps": [
                    {
                        "wait_webhook": "listen_webhook",
                        "webhook": "github",
                        "key": "42",
                    }
                ],
            }
        ),
        server_status=server_status,
        channel_sender=channel_sender,
    )

    result = use_case.execute("webhook_demo", flow_source="internal")

    assert result.status == FlowReadinessCheckStatus.VALID
    assert result.errors == []
    assert server_status.calls == 1
    assert channel_sender.calls == []


def test_returns_invalid_when_wait_webhook_flow_has_server_unavailable() -> None:
    server_status = _FakeServerStatus(available=False)
    channel_sender = _FakeChannelSender(available=True)
    use_case = FlowReadinessCheckerUseCase(
        runner=_FakeFlowRunner(
            {
                "name": "webhook_demo",
                "start": "listen_webhook",
                "steps": [
                    {
                        "wait_webhook": "listen_webhook",
                        "webhook": "github",
                        "key": "42",
                    }
                ],
            }
        ),
        server_status=server_status,
        channel_sender=channel_sender,
    )

    result = use_case.execute("webhook_demo", flow_source="internal")

    assert result.status == FlowReadinessCheckStatus.INVALID
    assert result.errors == [
        FlowReadinessCheckError(
            code="FLOW_SERVER_UNAVAILABLE",
            message=(
                "FLOW_SERVER_UNAVAILABLE: flow requires local server for "
                "wait_webhook (step=listen_webhook)"
            ),
        )
    ]
    assert server_status.calls == 1
    assert channel_sender.calls == []


def test_returns_invalid_when_wait_channel_flow_has_whatsapp_unavailable() -> None:
    server_status = _FakeServerStatus(available=True)
    channel_sender = _FakeChannelSender(available=False)
    use_case = FlowReadinessCheckerUseCase(
        runner=_FakeFlowRunner(
            {
                "name": "whatsapp_demo",
                "start": "listen_whatsapp",
                "steps": [
                    {
                        "wait_channel": "listen_whatsapp",
                        "channel": "whatsapp",
                        "key": "all",
                    }
                ],
            }
        ),
        server_status=server_status,
        channel_sender=channel_sender,
    )

    result = use_case.execute("whatsapp_demo", flow_source="internal")

    assert result.status == FlowReadinessCheckStatus.INVALID
    assert result.errors == [
        FlowReadinessCheckError(
            code="FLOW_WHATSAPP_UNAVAILABLE",
            message=(
                "FLOW_WHATSAPP_UNAVAILABLE: flow requires configured WhatsApp channel sender "
                "for wait_channel (step=listen_whatsapp)"
            ),
        )
    ]
    assert server_status.calls == 1
    assert channel_sender.calls == ["whatsapp"]


def test_returns_invalid_when_send_flow_has_whatsapp_unavailable() -> None:
    server_status = _FakeServerStatus(available=True)
    channel_sender = _FakeChannelSender(available=False)
    use_case = FlowReadinessCheckerUseCase(
        runner=_FakeFlowRunner(
            {
                "name": "whatsapp_send_demo",
                "start": "reply",
                "steps": [
                    {
                        "send": "reply",
                        "channel": "whatsapp",
                        "key": "chat-1",
                        "message": "hola",
                    }
                ],
            }
        ),
        server_status=server_status,
        channel_sender=channel_sender,
    )

    result = use_case.execute("whatsapp_send_demo", flow_source="internal")

    assert result.status == FlowReadinessCheckStatus.INVALID
    assert result.errors == [
        FlowReadinessCheckError(
            code="FLOW_WHATSAPP_UNAVAILABLE",
            message=(
                "FLOW_WHATSAPP_UNAVAILABLE: flow requires configured WhatsApp channel sender "
                "for send (step=reply)"
            ),
        )
    ]
    assert server_status.calls == 0
    assert channel_sender.calls == ["whatsapp"]
