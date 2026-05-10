from typing import Protocol

from skiller.domain.tool.channel_sender_model import ChannelSendResult


class ChannelSenderPort(Protocol):
    def is_available(
        self,
        *,
        channel: str,
    ) -> bool: ...

    def send_text(
        self,
        *,
        channel: str,
        key: str,
        message: str,
    ) -> ChannelSendResult: ...
