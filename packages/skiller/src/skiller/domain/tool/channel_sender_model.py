from dataclasses import dataclass


@dataclass(frozen=True)
class ChannelSendResult:
    channel: str
    key: str
    message: str
    message_id: str | None = None
