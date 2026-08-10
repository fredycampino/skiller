import pytest

from skiller.domain.agent.config.model import (
    AgentContextCompactionConfig,
    AgentContextConfig,
)
from skiller.domain.agent.context.model import AgentContextMetrics
from skiller.domain.agent.llm.model import LLMCustomModel
from skiller.domain.agent.llm.provider_registry import (
    BEDROCK_MODELS,
    CODEX_MODELS,
    MINIMAX_MODELS,
    AgentBedrockLLMModel,
    AgentBedrockProvider,
    AgentCodexLLMModel,
    AgentCodexProvider,
    AgentFakeLLMModel,
    AgentLLMProvider,
    AgentLLMProviderList,
    AgentLLMProviderType,
    AgentLMStudioProvider,
    AgentMiniMaxLLMModel,
    AgentMiniMaxProvider,
    AgentNullLLMModel,
    agent_llm_model_from_value,
)

pytestmark = pytest.mark.unit


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
    assert AgentCodexLLMModel.GPT_5_4.model_context_window_tokens == 1_050_000
    assert AgentCodexLLMModel.GPT_5_5.model_context_window_tokens == 1_050_000
    assert AgentBedrockLLMModel.CLAUDE_OPUS_4_6.model_context_window_tokens == 200_000


def test_agent_llm_model_rejects_unsupported_codex_model() -> None:
    with pytest.raises(ValueError, match="Unsupported LLM model: unsupported-codex"):
        agent_llm_model_from_value("unsupported-codex")


def test_agent_llm_providers_require_typed_model() -> None:
    with pytest.raises(
        TypeError,
        match="MiniMax LLM provider model must be an AgentMiniMaxLLMModel",
    ):
        AgentMiniMaxProvider(
            api_key="secret",
            model=AgentCodexLLMModel.GPT_5_5,
            models=MINIMAX_MODELS,
            timeout_seconds=30.0,
        )

    with pytest.raises(
        TypeError,
        match="Codex LLM provider model must be an AgentCodexLLMModel",
    ):
        AgentCodexProvider(
            credentials_file="/tmp/openai-codex.json",
            model=AgentMiniMaxLLMModel.M2_5,
            models=CODEX_MODELS,
            timeout_seconds=120.0,
        )

    with pytest.raises(
        TypeError,
        match="Bedrock LLM provider model must be an AgentBedrockLLMModel",
    ):
        AgentBedrockProvider(
            profile="claude-bedrock",
            model=AgentMiniMaxLLMModel.M2_5,
            models=BEDROCK_MODELS,
            timeout_seconds=30.0,
        )


def test_agent_llm_provider_rejects_model_outside_allowed_models() -> None:
    with pytest.raises(
        ValueError,
        match="LLM provider model is not allowed: MiniMax-M2.7",
    ):
        AgentMiniMaxProvider(
            api_key="secret",
            model=AgentMiniMaxLLMModel.M2_7,
            models=(AgentMiniMaxLLMModel.M2_5,),
            timeout_seconds=30.0,
        )


def test_agent_context_window_uses_smaller_model_limit() -> None:
    model = _lmstudio_model()
    context_larger_than_model = AgentContextConfig(
        window_width_tokens=200_000,
        compaction=AgentContextCompactionConfig(
            enabled=False,
            max_total_tokens_ratio=0.8,
            keep_last=5,
        ),
    )
    context_smaller_than_model = AgentContextConfig(
        window_width_tokens=100_000,
        compaction=AgentContextCompactionConfig(
            enabled=False,
            max_total_tokens_ratio=0.8,
            keep_last=5,
        ),
    )

    assert (
        context_larger_than_model.effective_context_tokens(
            model_context_window_tokens=model.model_context_window_tokens,
        )
        == 131_072
    )
    assert (
        context_larger_than_model.compaction_window_tokens(
            model_context_window_tokens=model.model_context_window_tokens,
        )
        == 104_857
    )
    assert (
        context_larger_than_model.tool_result_max_bytes(
            model_context_window_tokens=model.model_context_window_tokens,
        )
        == 50_000
    )
    assert context_larger_than_model.metrics(
        model_context_window_tokens=model.model_context_window_tokens,
    ) == AgentContextMetrics(
        effective_window_tokens=131_072,
        max_total_tokens_ratio=0.8,
    )
    assert (
        context_smaller_than_model.effective_context_tokens(
            model_context_window_tokens=model.model_context_window_tokens,
        )
        == 100_000
    )
    assert (
        context_smaller_than_model.compaction_window_tokens(
            model_context_window_tokens=model.model_context_window_tokens,
        )
        == 80_000
    )
    assert (
        context_smaller_than_model.tool_result_max_bytes(
            model_context_window_tokens=model.model_context_window_tokens,
        )
        == 40_000
    )
    assert context_smaller_than_model.metrics(
        model_context_window_tokens=model.model_context_window_tokens,
    ) == AgentContextMetrics(
        effective_window_tokens=100_000,
        max_total_tokens_ratio=0.8,
    )


def test_bedrock_provider_requires_profile() -> None:
    with pytest.raises(ValueError, match="Bedrock LLM provider requires profile"):
        AgentBedrockProvider(
            profile="   ",
            model=AgentBedrockLLMModel.CLAUDE_OPUS_4_6,
            models=BEDROCK_MODELS,
            timeout_seconds=30.0,
        )


def test_lmstudio_provider_requires_base_url() -> None:
    with pytest.raises(ValueError, match="LM Studio LLM provider requires base_url"):
        AgentLMStudioProvider(
            base_url="   ",
            model=_lmstudio_model(),
            models=(_lmstudio_model(),),
            timeout_seconds=30.0,
        )


def _minimax_provider() -> AgentLLMProvider:
    return AgentMiniMaxProvider(
        api_key="secret",
        model=AgentMiniMaxLLMModel.M2_5,
        models=MINIMAX_MODELS,
        timeout_seconds=30.0,
    )


def _lmstudio_model() -> LLMCustomModel:
    return LLMCustomModel(
        value="google/gemma-4-12b-qat",
        model_context_window_tokens=131_072,
    )
