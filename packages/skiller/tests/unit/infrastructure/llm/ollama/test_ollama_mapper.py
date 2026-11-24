from dataclasses import replace

import pytest

from skiller.domain.agent.llm.model import LLMUserMessage
from skiller.domain.agent.llm.provider_catalog import LLMModelParams, OllamaLLMModelDefinition
from skiller.domain.agent.llm.provider_ollama import OllamaLLMRequest
from skiller.infrastructure.llm.mapper.llm_usage_mapper import DefaultLLMUsageMapper
from skiller.infrastructure.llm.ollama.ollama_mapper import OllamaMapper

pytestmark = pytest.mark.unit

MODEL = OllamaLLMModelDefinition(
    model="qwen",
    context_window_tokens=32768,
    max_output_tokens=1024,
    params=None,
    effort_mapping=None,
)


def _request(model=MODEL, effort=None):
    return OllamaLLMRequest(model=model, messages=(LLMUserMessage("Hello"),), effort=effort)


def test_mapper_builds_options_from_model_params_without_dropping_zero_values():
    params = LLMModelParams(
        temperature=0,
        top_p=0.95,
        top_k=40,
        seed=0,
        repeat_penalty=1.1,
        stop=("END",),
    )
    model = replace(MODEL, params=params)
    mapper = OllamaMapper(usage_mapper=DefaultLLMUsageMapper(), keep_alive="5m")
    kwargs = mapper.to_kwargs(_request(model))
    assert kwargs["options"] == {
        "num_ctx": 32768,
        "num_predict": 1024,
        "temperature": 0,
        "top_p": 0.95,
        "top_k": 40,
        "seed": 0,
        "repeat_penalty": 1.1,
        "stop": ["END"],
    }
    assert kwargs["keep_alive"] == "5m"
    assert kwargs["stream"] is False
    assert model.params == params


def test_mapper_omits_unconfigured_values():
    model = replace(
        MODEL,
        max_output_tokens=None,
        params=LLMModelParams(
            temperature=None,
            top_p=None,
            top_k=None,
            seed=None,
            repeat_penalty=None,
            stop=None,
        ),
    )
    kwargs = OllamaMapper(usage_mapper=DefaultLLMUsageMapper(), keep_alive=None).to_kwargs(
        _request(model)
    )
    assert kwargs["options"] == {"num_ctx": 32768}
    assert "think" not in kwargs
    assert "keep_alive" not in kwargs


@pytest.mark.parametrize("effort", [1, 2, 3, 4, 5])
def test_mapper_selects_model_effort_level(effort):
    mapping = ("low", "low", "medium", "medium", "xhigh")
    model = replace(MODEL, effort_mapping=mapping)
    kwargs = OllamaMapper(usage_mapper=DefaultLLMUsageMapper(), keep_alive=None).to_kwargs(
        _request(model, effort)
    )
    assert kwargs["think"] == mapping[effort - 1]


@pytest.mark.parametrize("effort,mapping", [(None, None), (3, None), (None, (True,) * 5)])
def test_mapper_omits_think_without_effort_or_mapping(effort, mapping):
    kwargs = OllamaMapper(usage_mapper=DefaultLLMUsageMapper(), keep_alive=None).to_kwargs(
        _request(replace(MODEL, effort_mapping=mapping), effort)
    )
    assert "think" not in kwargs


@pytest.mark.parametrize("think", [True, False])
def test_mapper_preserves_boolean_think_and_zero_keep_alive(think):
    kwargs = OllamaMapper(usage_mapper=DefaultLLMUsageMapper(), keep_alive=0).to_kwargs(
        _request(replace(MODEL, effort_mapping=(think,) * 5), 1)
    )
    assert kwargs["think"] is think
    assert kwargs["keep_alive"] == 0


@pytest.mark.parametrize("effort", [0, 6, -1, True, 1.5])
def test_mapper_rejects_effort_outside_runtime_scale(effort):
    with pytest.raises(ValueError, match="integer from 1 to 5"):
        OllamaMapper(usage_mapper=DefaultLLMUsageMapper(), keep_alive=None).to_kwargs(
            _request(effort=effort)
        )
