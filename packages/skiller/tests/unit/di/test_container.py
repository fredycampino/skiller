import pytest

from skiller.di.container import _build_llm
from skiller.infrastructure.config.settings import Settings
from skiller.infrastructure.llm.fake_llm import FakeLLM
from skiller.infrastructure.llm.minimax_llm import MinimaxLLM
from skiller.infrastructure.llm.null_llm import NullLLM

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("provider", "expected_type"),
    [
        ("null", NullLLM),
        ("fake", FakeLLM),
        ("minimax", MinimaxLLM),
    ],
)
def test_build_llm_returns_expected_provider(provider: str, expected_type: type[object]) -> None:
    llm = _build_llm(
        Settings(
            llm_provider=provider,
            minimax_api_key="secret-key",
        )
    )

    assert isinstance(llm, expected_type)


def test_build_llm_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unsupported AGENT_LLM_PROVIDER"):
        _build_llm(Settings(llm_provider="unknown"))
