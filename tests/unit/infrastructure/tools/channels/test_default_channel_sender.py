from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError

import pytest

from skiller.infrastructure.config.settings import Settings
from skiller.infrastructure.tools.channels.default_channel_sender import DefaultChannelSender

pytestmark = pytest.mark.unit


class _FakeResponse:
    def __init__(self, payload: bytes, *, status: int = 200) -> None:
        self.payload = payload
        self.status = status

    def read(self) -> bytes:
        return self.payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        return None


def test_default_channel_sender_posts_to_whatsapp_bridge() -> None:
    sender = DefaultChannelSender(Settings(whatsapp_bridge_send_timeout_seconds=11.5))

    with patch(
        "skiller.infrastructure.tools.channels.default_channel_sender.urlopen",
        return_value=_FakeResponse(
            b'{"accepted": true, "channel": "whatsapp", "key": "chat-1", "message_id": "msg-1"}'
        ),
    ) as mock_urlopen:
        result = sender.send_text(channel="whatsapp", key="chat-1", message="hola")

    request = mock_urlopen.call_args.args[0]
    assert mock_urlopen.call_args.kwargs["timeout"] == 11.5
    assert request.full_url == "http://127.0.0.1:8002/messages"
    assert request.get_method() == "POST"
    assert request.data == b'{"channel": "whatsapp", "key": "chat-1", "text": "hola"}'
    assert result.channel == "whatsapp"
    assert result.key == "chat-1"
    assert result.message == "hola"
    assert result.message_id == "msg-1"


def test_default_channel_sender_reports_whatsapp_available_when_connected() -> None:
    sender = DefaultChannelSender(Settings())

    with patch(
        "skiller.infrastructure.tools.channels.default_channel_sender.urlopen",
        return_value=_FakeResponse(
            b'{"status": "connected", "paired": true, "qrCount": 0, "queueLength": 0}'
        ),
    ):
        result = sender.is_available(channel="whatsapp")

    assert result is True


def test_default_channel_sender_reports_whatsapp_unavailable_when_bridge_is_down() -> None:
    sender = DefaultChannelSender(Settings())

    with patch(
        "skiller.infrastructure.tools.channels.default_channel_sender.urlopen",
        side_effect=ValueError("down"),
    ):
        result = sender.is_available(channel="whatsapp")

    assert result is False


def test_default_channel_sender_rejects_unsupported_channel() -> None:
    sender = DefaultChannelSender(Settings())

    with pytest.raises(ValueError, match="Unsupported channel 'telegram'"):
        sender.send_text(channel="telegram", key="chat-1", message="hola")

    with pytest.raises(ValueError, match="Unsupported channel 'telegram'"):
        sender.is_available(channel="telegram")


def test_default_channel_sender_surfaces_bridge_errors() -> None:
    sender = DefaultChannelSender(Settings())
    error = HTTPError(
        url="http://127.0.0.1:8002/messages",
        code=409,
        msg="Conflict",
        hdrs=None,
        fp=BytesIO(b'{"accepted": false, "error": "bridge is not connected"}'),
    )

    with patch(
        "skiller.infrastructure.tools.channels.default_channel_sender.urlopen",
        side_effect=error,
    ):
        with pytest.raises(RuntimeError, match="bridge is not connected"):
            sender.send_text(channel="whatsapp", key="chat-1", message="hola")
