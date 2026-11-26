---
title: User LLM providers
description: Configure LLM connections, credentials, and available models.
---

This file is the catalog of LLM providers configured by the user: it defines how to connect to each provider and which models it offers.

Authentication creates or updates this file at `~/.skiller/settings/providers.json`. Use `SKILLER_AGENT_PROVIDERS_FILE` to apply another override file:

```bash
SKILLER_AGENT_PROVIDERS_FILE=~/custom-providers.json skiller run @flows
```

The file must exist. Its values override the included catalog and the user configuration; omitted fields keep their previously configured values.

## Built-in providers

Skiller includes these provider definitions. Use authentication to configure credentials or discover local models as required:

| Provider | Adapter |
| --- | --- |
| MiniMax (`minimax`) | `openai` |
| Moonshot (`moonshot`) | `openai` |
| DeepSeek (`deepseek`) | `openai` |
| OpenRouter (`openrouter`) | `openai` |
| LM Studio (`lmstudio`) | `openai` |
| OpenAI Codex (`codex`) | `codex` |
| Amazon Bedrock (`bedrock`) | `bedrock` |
| Ollama (`ollama`) | `ollama` |

See [Supported LLM APIs](/docs/configuration/supported-llm-apis/) for the API used by each adapter.

## Override or add a provider

Entries are matched by provider name:

- **Override a built-in provider:** use its existing name, such as `ollama` or `bedrock`. Omit `adapter` to inherit it. Supplied fields replace the catalog values; omitted fields retain their inherited values. A `models` list replaces the entire inherited list, rather than adding individual models.
- **Add a provider:** choose a new name, such as `my-ollama`, and declare a supported `adapter` with its required configuration. This creates a separate connection without changing the built-in provider. It does not add a new adapter implementation.

To define additional connections, follow the adapter documentation: [OpenAI](/docs/configuration/openai-adapter/), [Codex](/docs/configuration/codex-adapter/), [Bedrock](/docs/configuration/bedrock-adapter/), or [Ollama](/docs/configuration/ollama-adapter/).

## Example provider overrides

This `providers.json` example overrides built-in catalog providers with user credentials, connection settings, and local models:

```json
{
  "providers": {
    "bedrock": {
      "profile": "work",
      "timeout_seconds": 120
    },
    "codex": {
      "credentials_file": "~/.skiller/secrets/openai-codex.json",
      "timeout_seconds": 120
    },
    "deepseek": {
      "api_key_file": "~/.skiller/secrets/deepseek_api_key",
      "timeout_seconds": 60
    },
    "lmstudio": {
      "base_url": "http://127.0.0.1:1234/v1",
      "models": [
        {
          "context_window_tokens": 262144,
          "model": "qwen3.8-27b"
        },
        {
          "context_window_tokens": 262144,
          "model": "ornith-1.0-9b"
        },
        {
          "context_window_tokens": 262144,
          "model": "mistralai/ministral-3-14b-reasoning"
        },
        {
          "context_window_tokens": 262144,
          "model": "google/gemma-4-12b-qat"
        }
      ],
      "timeout_seconds": 120
    },
    "ollama": {
      "models": [
        {
          "model": "hf.co/unsloth/Qwen3.8-27B-GGUF:UD-Q6_K",
          "context_window_tokens": 32768,
          "effort_mapping": ["low", "low", "medium", "medium", "xhigh"]
        }
      ]
    },
    "minimax": {
      "api_key_file": "~/.skiller/secrets/minimax_api_key",
      "timeout_seconds": 60
    },
    "moonshot": {
      "api_key_file": "~/.skiller/secrets/moonshot_api_key",
      "timeout_seconds": 60
    }
  }
}
```

Ollama inherits the local server URL and timeout from the catalog. Its user configuration must include at least one installed model; `/auth ollama` discovers and writes this list.

See [OpenAI adapter](/docs/configuration/openai-adapter/) and [Ollama adapter](/docs/configuration/ollama-adapter/) for their connection settings and model options.
