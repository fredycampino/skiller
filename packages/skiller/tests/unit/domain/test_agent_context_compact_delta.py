import pytest

from skiller.domain.agent.context.compact_delta import estimate_delta_tokens_from_chars

pytestmark = pytest.mark.unit


def test_estimate_delta_tokens_from_chars_returns_zero_without_block_chars() -> None:
    assert estimate_delta_tokens_from_chars(
        block_chars=0,
    ) == 0
