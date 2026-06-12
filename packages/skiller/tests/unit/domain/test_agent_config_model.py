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
    AgentBedrockLLMModel,
    AgentBedrockProvider,
    AgentCodexLLMModel,
    AgentCodexProvider,
    AgentFakeLLMModel,
    AgentLLMProvider,
    AgentLLMProviderList,
    AgentLLMProviderType,
    AgentMiniMaxLLMModel,
    AgentMiniMaxProvider,
    AgentNullLLMModel,
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
    assert provider.model == AgentMiniMaxLLMModel.M2_5
    assert provider.timeout_seconds == 30.0
    assert provider.window_width_tokens == 1_000_000
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


def test_agent_llm_models_define_model_context_window_tokens() -> None:
    assert AgentNullLLMModel.NULL1.model_context_window_tokens == 100_000
    assert AgentFakeLLMModel.MODEL1.model_context_window_tokens == 100_000
    assert AgentMiniMaxLLMModel.M2_5.model_context_window_tokens == 204_800
    assert AgentMiniMaxLLMModel.M2_7.model_context_window_tokens == 204_800
    assert AgentCodexLLMModel.GPT_5_3_CODEX.model_context_window_tokens == 400_000
    assert AgentCodexLLMModel.GPT_5_4.model_context_window_tokens == 1_050_000
    assert AgentCodexLLMModel.GPT_5_5.model_context_window_tokens == 1_050_000
    assert AgentBedrockLLMModel.CLAUDE_OPUS_4_6.model_context_window_tokens == 200_000


def test_agent_llm_providers_require_typed_model_enum() -> None:
    with pytest.raises(
        TypeError,
        match="MiniMax LLM provider model must be an AgentMiniMaxLLMModel",
    ):
        AgentMiniMaxProvider(
            api_key="secret",
            model=AgentCodexLLMModel.GPT_5_5,
            timeout_seconds=30.0,
            window_width_tokens=1_000_000,
        )

    with pytest.raises(
        TypeError,
        match="Codex LLM provider model must be an AgentCodexLLMModel",
    ):
        AgentCodexProvider(
            credentials_file="/tmp/openai-codex.json",
            model=AgentMiniMaxLLMModel.M2_5,
            timeout_seconds=120.0,
            window_width_tokens=1_000_000,
        )

    with pytest.raises(
        TypeError,
        match="Bedrock LLM provider model must be an AgentBedrockLLMModel",
    ):
        AgentBedrockProvider(
            profile="claude-bedrock",
            model=AgentMiniMaxLLMModel.M2_5,
            timeout_seconds=30.0,
            window_width_tokens=1_000_000,
        )


def test_bedrock_provider_requires_profile() -> None:
    with pytest.raises(ValueError, match="Bedrock LLM provider requires profile"):
        AgentBedrockProvider(
            profile="   ",
            model=AgentBedrockLLMModel.CLAUDE_OPUS_4_6,
            timeout_seconds=30.0,
            window_width_tokens=1_000_000,
        )


def _minimax_provider() -> AgentLLMProvider:
    return AgentMiniMaxProvider(
        api_key="secret",
        model=AgentMiniMaxLLMModel.M2_5,
        timeout_seconds=30.0,
        window_width_tokens=1_000_000,
    )
