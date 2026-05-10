import pytest
from skiller.application.agent.config.output_truncator import OutputTruncator

pytestmark = pytest.mark.unit


def test_output_truncator_truncates_text() -> None:
    truncator = OutputTruncator()

    result = truncator.truncate_text("abcdefghijklmnopqrstuvwxyz", max_chars=10)

    assert result == "abcdefghij..."


def test_output_truncator_truncates_list_items() -> None:
    truncator = OutputTruncator()

    result = truncator.truncate_list([1, 2, 3, 4], max_items=2)

    assert result == [1, 2]


def test_output_truncator_caps_large_json_payload() -> None:
    truncator = OutputTruncator()

    result = truncator.cap_json_payload({"k": "v" * 50}, max_chars=20)

    assert result["truncated"] is True
    assert isinstance(result["preview"], str)
    assert result["preview"].endswith("...")
