import pytest

from skiller.infrastructure.tools.channels.default_channel_sender import DefaultChannelSender

pytestmark = pytest.mark.unit


def test_default_channel_sender_reports_channels_unavailable() -> None:
    sender = DefaultChannelSender()

    assert sender.is_available(channel="whatsapp") is False
    assert sender.is_available(channel="telegram") is False


def test_default_channel_sender_fails_when_sending_without_configuration() -> None:
    sender = DefaultChannelSender()

    with pytest.raises(RuntimeError, match="Channel sending is not configured"):
        sender.send_text(channel="whatsapp", key="chat-1", message="hola")
