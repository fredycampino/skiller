#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../../.."

runtime_python="${SKILLER_RUNTIME_PYTHON:-./.venv/bin/python}"
api_key_file="${OPENROUTE_API_KEY_FILE:-${HOME}/.skiller/secrets/openroute_api_key}"

if [[ "${RUN_PROVIDER_E2E:-0}" != "1" && "${RUN_OPENROUTER_PROVIDER_E2E:-0}" != "1" ]]; then
  python3 - <<'PY'
import json

print(json.dumps({
    "status": "SKIPPED",
    "reason": "set RUN_PROVIDER_E2E=1 or RUN_OPENROUTER_PROVIDER_E2E=1 to run OpenRouter provider e2e",
}, indent=2))
PY
  exit 0
fi

if [[ ! -x "${runtime_python}" ]]; then
  printf 'Missing runtime python: %s\n' "${runtime_python}" >&2
  exit 1
fi

if [[ -z "${OPENROUTER_API_KEY:-}" && -z "${OPENROUTE_API_KEY:-}" && ! -f "${api_key_file}" ]]; then
  python3 - <<'PY'
import json

print(json.dumps({
    "status": "SKIPPED",
    "reason": "OPENROUTER_API_KEY is not configured and the OpenRouter api key file does not exist",
}, indent=2))
PY
  exit 0
fi

if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
  if [[ -n "${OPENROUTE_API_KEY:-}" ]]; then
    OPENROUTER_API_KEY="${OPENROUTE_API_KEY}"
  else
    OPENROUTER_API_KEY="$(<"${api_key_file}")"
  fi
  export OPENROUTER_API_KEY
fi

PYTHONPATH=packages/skiller/src \
"${runtime_python}" - <<'PY'
import json
import os
from pathlib import Path

from skiller.domain.agent.llm.finish_type import LLMFinishType
from skiller.domain.agent.llm.model import LLMToolChoiceMode, LLMUserMessage
from skiller.domain.agent.llm.request import OpenAILLMRequest
from skiller.infrastructure.config.file_llm_provider_catalog_datasource import (
    FileLLMProviderCatalogDatasource,
)
from skiller.infrastructure.config.file_llm_provider_catalog_mapper import (
    FileLLMProviderCatalogMapper,
)
from skiller.infrastructure.llm.default_llm_client_resolver import DefaultLLMClientResolver
from skiller.infrastructure.llm.openai.openai_api_key_datasource import (
    OpenAIApiKeyDatasource,
)


catalog_path = Path(
    "packages/skiller/src/skiller/application/config/providers.json"
)
catalog = FileLLMProviderCatalogDatasource(
    mapper=FileLLMProviderCatalogMapper(),
).get_providers(catalog_path)
provider = next(provider for provider in catalog if provider.name == "openrouter")
model_name = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o")
model = next(model for model in provider.models if model.model == model_name)

client = DefaultLLMClientResolver(
    api_key_datasource=OpenAIApiKeyDatasource(env=os.environ),
).resolve(provider)
response = client.generate(
    OpenAILLMRequest(
        model=model,
        messages=(LLMUserMessage("What is the meaning of life?"),),
        tool_choice=LLMToolChoiceMode.AUTO,
        parallel_tool_calls=provider.parallel_tool_calls,
        temperature=provider.temperature,
        top_p=provider.top_p,
    )
)

if response.finish_type != LLMFinishType.STOP:
    raise SystemExit(response.error or "OpenRouter chat completion failed")
if not response.content or not response.content.strip():
    raise SystemExit("OpenRouter response did not include text content")

print(
    json.dumps(
        {
            "status": "SUCCEEDED",
            "provider": provider.name,
            "adapter": provider.adapter.value,
            "model": response.model.value,
            "finish_type": response.finish_type.value,
            "content": response.content,
            "usage": None
            if response.usage is None
            else {
                "prompt_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        },
        indent=2,
        sort_keys=True,
    )
)
PY
