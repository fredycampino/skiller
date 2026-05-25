import pytest

from skiller.application.use_cases.ingress.handle_channel import HandleChannelResult
from skiller.application.waits.channel_mapper import ChannelWaitMapper

pytestmark = pytest.mark.unit


def test_mapper_builds_handle_channel_and_output() -> None:
    mapper = ChannelWaitMapper()

    request = mapper.to_handle_input(
        " whatsapp ",
        " 123 ",
        {"text": "hello"},
        external_id="msg-1",
        dedup_key=" dedup-1 ",
    )
    result = HandleChannelResult(
        accepted=True,
        duplicate=False,
        run_ids=["run-1"],
    )

    assert request.channel == "whatsapp"
    assert request.key == "123"
    assert request.payload == {"text": "hello"}
    assert request.external_id == "msg-1"
    assert request.dedup_key == "dedup-1"
    assert mapper.to_handle_dict(request, result) == {
        "accepted": True,
        "duplicate": False,
        "channel": "whatsapp",
        "key": "123",
        "matched_runs": ["run-1"],
        "external_id": "msg-1",
    }
