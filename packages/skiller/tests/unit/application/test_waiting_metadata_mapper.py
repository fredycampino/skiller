import pytest

from skiller.application.waits.waiting_metadata_mapper import (
    WaitingMetadataMapper,
    WaitingStatus,
)
from skiller.application.waits.waiting_metadata_resolver import (
    ChannelWaitingMetadata,
    InputWaitingMetadata,
    WebhookWaitingMetadata,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        (None, WaitingStatus(wait_type="none")),
        (
            InputWaitingMetadata(prompt="Continue?"),
            WaitingStatus(wait_type="input", prompt="Continue?"),
        ),
        (
            WebhookWaitingMetadata(webhook="github", key="main"),
            WaitingStatus(wait_type="webhook"),
        ),
        (
            ChannelWaitingMetadata(channel="chat", key="general"),
            WaitingStatus(wait_type="channel"),
        ),
    ],
)
def test_waiting_metadata_mapper_returns_status_fields(metadata, expected) -> None:  # noqa: ANN001
    assert WaitingMetadataMapper().to_status(metadata) == expected
