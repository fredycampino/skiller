#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../../.."
if [[ "${RUN_PROVIDER_E2E:-0}" != "1" && "${RUN_OLLAMA_PROVIDER_E2E:-0}" != "1" ]]; then
  printf '%s\n' '{"status":"SKIPPED","reason":"set RUN_OLLAMA_PROVIDER_E2E=1"}'
  exit 0
fi
"${SKILLER_RUNTIME_PYTHON:-./.venv/bin/python}" - <<'PY'
import importlib.util
import json
import os
import tempfile
from pathlib import Path

from skiller.application.agent.llmodel.llm_model_manager import LLMModelManager
from skiller.domain.agent.llm.finish_type import LLMFinishType
from skiller.domain.agent.llm.model import LLMUserMessage
from skiller.domain.agent.llm.provider_ollama import OllamaLLMRequest
from skiller.infrastructure.config.file_llm_provider_catalog_datasource import FileLLMProviderCatalogDatasource
from skiller.infrastructure.config.file_llm_provider_catalog_mapper import FileLLMProviderCatalogMapper
from skiller.infrastructure.config.file_llm_provider_catalog_port import FileLLMProviderCatalogPort
from skiller.infrastructure.llm.default_llm_client_resolver import DefaultLLMClientResolver
from skiller.infrastructure.llm.openai.openai_api_key_datasource import OpenAIApiKeyDatasource
from skiller.domain.tool.tool_contract import ToolDefinition, ToolSchema, ToolRequest, ToolRequestResult

class ProbeTool(ToolDefinition):
    name = "get_weather"
    description = "Returns current weather for a city."
    def schema(self):
        return ToolSchema(value={"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]})
    def request(self, input):
        return ToolRequestResult.valid(ToolRequest())

spec = importlib.util.spec_from_file_location("ollama_auth", "apps/agents/auths/ollama/ollama_auth.py")
auth = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auth)
with tempfile.TemporaryDirectory(prefix="skiller-ollama-provider-") as directory:
    root = Path(directory)
    auth.providers_file = lambda: root / "providers.json"
    auth.agent_config_file = lambda: root / "agent.json"
    auth.backup_configuration("test-run")
    result = auth.configure(os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"), "test-run")
    mapper = FileLLMProviderCatalogMapper()
    catalog = FileLLMProviderCatalogPort(
        datasource=FileLLMProviderCatalogDatasource(mapper=mapper), mapper=mapper,
        default_path=Path("packages/skiller/src/skiller/application/config/providers.json"),
        user_path=auth.providers_file(), env={},
    ).get_catalog()
    provider = catalog.get("ollama")
    model = catalog.get_model(provider_name="ollama", model_name=os.environ.get("OLLAMA_MODEL", result["model"]))
    response = LLMModelManager(client_resolver=DefaultLLMClientResolver(
        api_key_datasource=OpenAIApiKeyDatasource(env={}),
    )).generate(provider=provider, request=OllamaLLMRequest(
        model=model, messages=(LLMUserMessage("Call get_weather with city Madrid. Do not answer without calling it."),),
        tools=(ProbeTool(),),
    ))
    assert response.finish_type == LLMFinishType.TOOL_CALLS, response.error or response.content
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].function.name == "get_weather"
    assert json.loads(response.tool_calls[0].function.arguments_json) == {"city": "Madrid"}
    assert response.usage.total_tokens > 0
    assert response.generation_metrics.output_generation_duration_ns > 0
    print(json.dumps({"status": "SUCCEEDED", "provider": "ollama", "model": model.value,
                      "total_tokens": response.usage.total_tokens}, indent=2))
PY
