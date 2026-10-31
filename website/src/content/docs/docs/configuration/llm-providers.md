---
title: User LLM providers
description: Configure LLM connections, credentials, and available models.
---

This file is the catalog of LLM providers configured by the user: it defines how to connect to each provider and which models it offers.

Authentication creates or updates this file at `~/.skiller/settings/providers.json`. Use `AGENT_PROVIDERS_FILE` to apply another override file:

```bash
AGENT_PROVIDERS_FILE=~/custom-providers.json skiller run @flows
```

The file must exist. Its values override the included catalog and the user configuration; omitted fields keep their previously configured values.

## Built-in providers

Skiller includes these provider definitions. Configure their credentials to use them:

| Provider | Adapter |
| --- | --- |
| MiniMax (`minimax`) | `openai` |
| Moonshot (`moonshot`) | `openai` |
| DeepSeek (`deepseek`) | `openai` |
| OpenRouter (`openrouter`) | `openai` |
| LM Studio (`lmstudio`) | `openai` |
| OpenAI Codex (`codex`) | `codex` |
| Amazon Bedrock (`bedrock`) | `bedrock` |

See [Supported LLM APIs](/docs/configuration/supported-llm-apis/) for the API used by each adapter.

## Example providers.json

This example shows the catalog of a user who has configured authentication for several providers and added local models through LM Studio:

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

See [OpenAI adapter](/docs/configuration/openai-adapter/) for its provider fields, credentials, models, and options.
