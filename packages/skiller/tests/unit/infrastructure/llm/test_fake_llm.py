import pytest

from skiller.infrastructure.llm.fake_llm import FakeLLM

pytestmark = pytest.mark.unit


def test_fake_llm_returns_configured_json_payload() -> None:
    llm = FakeLLM(
        response_json='{"summary":"ok","severity":"low","next_action":"retry"}',
        model="fake-test",
    )

    result = llm.generate(
        [
            {"role": "system", "content": "Return JSON"},
            {"role": "user", "content": "Analyze"},
        ]
    )

    assert result == {
        "ok": True,
        "content": '{"summary":"ok","severity":"low","next_action":"retry"}',
        "model": "fake-test",
    }
