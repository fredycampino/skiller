from dataclasses import dataclass

from skiller.application.waits.waiting_metadata_resolver import (
    ChannelWaitingMetadata,
    InputWaitingMetadata,
    WaitingMetadata,
    WebhookWaitingMetadata,
)


@dataclass(frozen=True, kw_only=True)
class WaitingStatus:
    wait_type: str
    prompt: str = ""


class WaitingMetadataMapper:
    def to_status(self, metadata: WaitingMetadata | None) -> WaitingStatus:
        if isinstance(metadata, InputWaitingMetadata):
            return WaitingStatus(wait_type="input", prompt=metadata.prompt)
        if isinstance(metadata, WebhookWaitingMetadata):
            return WaitingStatus(wait_type="webhook")
        if isinstance(metadata, ChannelWaitingMetadata):
            return WaitingStatus(wait_type="channel")
        return WaitingStatus(wait_type="none")
