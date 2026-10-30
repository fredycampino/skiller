---
title: LLM providers
description: Configure LLM connections, credentials, and available models.
---

Provider configuration defines the LLM connections and models available to your agents. Customize the included catalog in `~/.skiller/settings/providers.json`, or use `AGENT_PROVIDERS_FILE` to apply another override file:

```bash
AGENT_PROVIDERS_FILE=~/custom-providers.json skiller run @flows
```

The file must exist. Its values override the included catalog and the user configuration; omitted fields keep their previously configured values.

## Configuration file

This example updates an existing provider. Fields you omit keep their values from the included catalog:

```json
{
  "providers": {
    "minimax": {
      "api_key_file": "~/.skiller/secrets/minimax_api_key",
      "timeout_seconds": 60,
      "models": [
        {
          "model": "MiniMax-M3.1-Flash",
          "context_window_tokens": 1000000,
          "max_output_tokens": 4096
        }
      ]
    }
  }
}
```

## Providers

Each key under `providers` identifies a provider, such as `minimax`, `deepseek`, or `openrouter`.

| Field | Description | Default |
| --- | --- | --- |
| `enabled` | Makes the provider available. | From the included catalog |
| `timeout_seconds` | Request timeout in seconds. | From the included catalog |

For example, disable a provider:

```json
{
  "providers": {
    "moonshot": {
      "enabled": false
    }
  }
}
```

## Credentials

For OpenAI-compatible providers, choose one API key source:

| Field | Description | Default |
| --- | --- | --- |
| `api_key_file` | Path to a file containing the API key. | From the included catalog |
| `api_key_env` | Name of the environment variable containing the API key. | From the included catalog |
| `api_key` | Literal API key; prefer a file or environment variable. | From the included catalog |

Use a private file containing only the key:

```json
{
  "providers": {
    "minimax": {
      "api_key_file": "~/.skiller/secrets/minimax_api_key"
    }
  }
}
```

Or reference an environment variable available to the Skiller process:

```json
{
  "providers": {
    "minimax": {
      "api_key_env": "AGENT_MINIMAX_API_KEY"
    }
  }
}
```

Setting a key source replaces the inherited source. Do not set multiple sources in the same provider entry.

Codex uses a `credentials_file`; Bedrock uses an AWS `profile`. For guided authentication, see [Add an LLM provider](/docs/getting-started/add-an-llm-provider/).

## Models

Each provider has a list of available models. Defining `models` replaces that provider's entire model list.

| Field | Description | Default |
| --- | --- | --- |
| `model` | Model identifier accepted by the provider. | Required for each model entry |
| `context_window_tokens` | Context window size in tokens. | Required for each model entry |
| `max_output_tokens` | Output token limit. | Not set; the provider determines the limit |

For example, keep a single model with an explicit output limit:

```json
{
  "providers": {
    "minimax": {
      "models": [
        {
          "model": "MiniMax-M3.1-Flash",
          "context_window_tokens": 1000000,
          "max_output_tokens": 4096
        }
      ]
    }
  }
}
```

To connect another service, see [Custom LLM providers](/docs/configuration/custom-llm-providers/).
