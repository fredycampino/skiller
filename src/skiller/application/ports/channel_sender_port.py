from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ChannelSendResult:
    channel: str
    key: str
    message: str
    message_id: str | None = None


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
