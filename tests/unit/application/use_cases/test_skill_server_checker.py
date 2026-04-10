import pytest

from skiller.application.use_cases.skill_server_checker import (
    SkillServerCheckError,
    SkillServerCheckerUseCase,
    SkillServerCheckStatus,
)

pytestmark = pytest.mark.unit


class _FakeSkillRunner:
    def __init__(self, skill: object) -> None:
        self.skill = skill
        self.calls: list[dict[str, str]] = []

    def load_skill(self, skill_source: str, skill_ref: str) -> object:
        self.calls.append({"skill_source": skill_source, "skill_ref": skill_ref})
        return self.skill


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


def test_returns_valid_when_skill_does_not_use_server_steps() -> None:
    server_status = _FakeServerStatus(available=False)
    channel_sender = _FakeChannelSender(available=False)
    use_case = SkillServerCheckerUseCase(
        skill_runner=_FakeSkillRunner(
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

    result = use_case.execute("notify_test", skill_source="internal")

    assert result.status == SkillServerCheckStatus.VALID
    assert result.errors == []
    assert server_status.calls == 0
    assert channel_sender.calls == []


def test_returns_valid_when_wait_channel_skill_has_server_available() -> None:
    server_status = _FakeServerStatus(available=True)
    channel_sender = _FakeChannelSender(available=True)
    use_case = SkillServerCheckerUseCase(
        skill_runner=_FakeSkillRunner(
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

    result = use_case.execute("whatsapp_demo", skill_source="internal")

    assert result.status == SkillServerCheckStatus.VALID
    assert result.errors == []
    assert server_status.calls == 1
    assert channel_sender.calls == ["whatsapp"]


def test_returns_invalid_when_wait_channel_skill_has_server_unavailable() -> None:
    server_status = _FakeServerStatus(available=False)
    channel_sender = _FakeChannelSender(available=True)
    use_case = SkillServerCheckerUseCase(
        skill_runner=_FakeSkillRunner(
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

    result = use_case.execute("whatsapp_demo", skill_source="internal")

    assert result.status == SkillServerCheckStatus.INVALID
    assert result.errors == [
        SkillServerCheckError(
            code="SKILL_SERVER_UNAVAILABLE",
            message=(
                "SKILL_SERVER_UNAVAILABLE: skill requires local server for wait_channel "
                "(step=listen_whatsapp)"
            ),
        )
    ]
    assert server_status.calls == 1
    assert channel_sender.calls == []


def test_returns_valid_when_wait_webhook_skill_has_server_available() -> None:
    server_status = _FakeServerStatus(available=True)
    channel_sender = _FakeChannelSender(available=False)
    use_case = SkillServerCheckerUseCase(
        skill_runner=_FakeSkillRunner(
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

    result = use_case.execute("webhook_demo", skill_source="internal")

    assert result.status == SkillServerCheckStatus.VALID
    assert result.errors == []
    assert server_status.calls == 1
    assert channel_sender.calls == []


def test_returns_invalid_when_wait_webhook_skill_has_server_unavailable() -> None:
    server_status = _FakeServerStatus(available=False)
    channel_sender = _FakeChannelSender(available=True)
    use_case = SkillServerCheckerUseCase(
        skill_runner=_FakeSkillRunner(
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

    result = use_case.execute("webhook_demo", skill_source="internal")

    assert result.status == SkillServerCheckStatus.INVALID
    assert result.errors == [
        SkillServerCheckError(
            code="SKILL_SERVER_UNAVAILABLE",
            message=(
                "SKILL_SERVER_UNAVAILABLE: skill requires local server for "
                "wait_webhook (step=listen_webhook)"
            ),
        )
    ]
    assert server_status.calls == 1
    assert channel_sender.calls == []


def test_returns_invalid_when_wait_channel_skill_has_whatsapp_unavailable() -> None:
    server_status = _FakeServerStatus(available=True)
    channel_sender = _FakeChannelSender(available=False)
    use_case = SkillServerCheckerUseCase(
        skill_runner=_FakeSkillRunner(
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

    result = use_case.execute("whatsapp_demo", skill_source="internal")

    assert result.status == SkillServerCheckStatus.INVALID
    assert result.errors == [
        SkillServerCheckError(
            code="SKILL_WHATSAPP_UNAVAILABLE",
            message=(
                "SKILL_WHATSAPP_UNAVAILABLE: skill requires active WhatsApp bridge "
                "for wait_channel (step=listen_whatsapp)"
            ),
        )
    ]
    assert server_status.calls == 1
    assert channel_sender.calls == ["whatsapp"]


def test_returns_invalid_when_send_skill_has_whatsapp_unavailable() -> None:
    server_status = _FakeServerStatus(available=True)
    channel_sender = _FakeChannelSender(available=False)
    use_case = SkillServerCheckerUseCase(
        skill_runner=_FakeSkillRunner(
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

    result = use_case.execute("whatsapp_send_demo", skill_source="internal")

    assert result.status == SkillServerCheckStatus.INVALID
    assert result.errors == [
        SkillServerCheckError(
            code="SKILL_WHATSAPP_UNAVAILABLE",
            message=(
                "SKILL_WHATSAPP_UNAVAILABLE: skill requires active WhatsApp bridge "
                "for send (step=reply)"
            ),
        )
    ]
    assert server_status.calls == 0
    assert channel_sender.calls == ["whatsapp"]
