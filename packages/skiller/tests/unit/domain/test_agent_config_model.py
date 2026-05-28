import pytest

from skiller.domain.agent.agent_config_model import (
    AgentConfig,
    AgentContextCompactionConfig,
    AgentContextConfig,
    AgentEventOutputConfig,
    AgentEventOutputTruncateConfig,
    AgentLoopConfig,
)
from skiller.domain.agent.agent_llm_provider_model import (
    AgentLLMProvider,
    AgentLLMProviderList,
    AgentLLMProviderType,
)

pytestmark = pytest.mark.unit


def test_agent_config_uses_runtime_defaults_for_agent_sections() -> None:
    config = AgentConfig(
        llm=AgentLLMProviderList(
            default_provider=AgentLLMProviderType.MINIMAX,
            providers=(_minimax_provider(),),
        ),
    )

    assert config.llm.default_provider == AgentLLMProviderType.MINIMAX
    assert config.llm.default().api_key == "secret"
    assert config.loop.max_turns == 10
    assert config.loop.max_tool_calls == 5
    assert config.context.compaction.enabled is False
    assert config.context.compaction.max_total_tokens_ratio == 0.8
    assert config.event_output.truncate.enabled is True
    assert config.event_output.truncate.max_text_chars == 600
    assert config.event_output.truncate.max_json_chars == 4000
    assert config.event_output.truncate.max_array_items == 20


def test_agent_config_accepts_explicit_sections() -> None:
    config = AgentConfig(
        llm=AgentLLMProviderList(
            default_provider=AgentLLMProviderType.MINIMAX,
            providers=(_minimax_provider(),),
        ),
        loop=AgentLoopConfig(max_turns=20, max_tool_calls=7),
        context=AgentContextConfig(
            compaction=AgentContextCompactionConfig(
                enabled=True,
                max_total_tokens_ratio=0.9,
            ),
        ),
        event_output=AgentEventOutputConfig(
            truncate=AgentEventOutputTruncateConfig(
                enabled=False,
                max_text_chars=300,
                max_json_chars=2000,
                max_array_items=8,
            ),
        ),
    )

    provider = config.llm.default()

    assert config.llm.default_provider == AgentLLMProviderType.MINIMAX
    assert provider.api_key == "secret"
    assert provider.model == "MiniMax-M2.5"
    assert provider.timeout_seconds == 30.0
    assert provider.context_window_tokens == 1_000_000
    assert config.loop.max_turns == 20
    assert config.loop.max_tool_calls == 7
    assert config.context.compaction.enabled is True
    assert config.context.compaction.max_total_tokens_ratio == 0.9
    assert config.event_output.truncate.enabled is False
    assert config.event_output.truncate.max_text_chars == 300
    assert config.event_output.truncate.max_json_chars == 2000
    assert config.event_output.truncate.max_array_items == 8


def test_agent_llm_provider_list_requires_default_provider() -> None:
    with pytest.raises(RuntimeError, match="Missing default LLM provider config: codex"):
        AgentLLMProviderList(
            default_provider=AgentLLMProviderType.CODEX,
            providers=(_minimax_provider(),),
        )


def _minimax_provider() -> AgentLLMProvider:
    return AgentLLMProvider(
        type=AgentLLMProviderType.MINIMAX,
        api_key="secret",
        model="MiniMax-M2.5",
        timeout_seconds=30.0,
        context_window_tokens=1_000_000,
    )
