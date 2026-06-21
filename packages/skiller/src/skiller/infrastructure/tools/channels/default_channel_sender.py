from skiller.domain.tool.channel_sender_model import ChannelSendResult
from skiller.domain.tool.channel_sender_port import ChannelSenderPort


class DefaultChannelSender(ChannelSenderPort):
    def is_available(
        self,
        *,
        channel: str,
    ) -> bool:
        return False

    def send_text(
        self,
        *,
        channel: str,
        key: str,
        message: str,
    ) -> ChannelSendResult:
        raise RuntimeError("Channel sending is not configured")
