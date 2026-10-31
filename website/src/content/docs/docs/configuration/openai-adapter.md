---
title: OpenAI adapter
description: Configure providers that use the OpenAI-compatible Chat Completions API.
---

Uses the OpenAI-compatible Chat Completions API. MiniMax, Moonshot, DeepSeek, OpenRouter, and LM Studio use this adapter.

## Provider section shape

Add the provider definition to your [user provider catalog](/docs/configuration/llm-providers/):

```json
{
  "providers": {
    "my-provider": {
      "adapter": "openai",
      "enabled": true,
      "base_url": "https://llm.example.com/v1",
      "api_key_env": "MY_PROVIDER_API_KEY",
      "timeout_seconds": 60,
      "temperature": 1,
      "top_p": 1,
      "parallel_tool_calls": true,
      "tool_choice": "auto",
      "options": {},
      "models": [
        {
          "model": "my-model",
          "context_window_tokens": 128000,
          "max_output_tokens": 4096
        }
      ]
    }
  }
}
```

This example defines a new provider. When customizing a built-in provider, omit adapter and include only the fields you want to change.

## Provider fields

Fields omitted from a built-in provider keep their catalog values; there is no single default shared by all providers.

| Field | Description | Default |
| --- | --- | --- |
| `enabled` | Makes the provider available. | From the included catalog |
| `base_url` | Chat Completions API base URL. | From the included catalog |
| `timeout_seconds` | Positive request timeout in seconds. | From the included catalog |
| `temperature` | Sampling temperature, zero or greater. | From the included catalog |
| `top_p` | Nucleus sampling probability, greater than 0 and at most 1. | From the included catalog |
| `parallel_tool_calls` | Requests support for parallel tool calls. | From the included catalog |
| `tool_choice` | Tool selection mode: auto, required, or none. | From the included catalog |
| `options` | Provider-specific body parameters, sent as extra_body. | From the catalog; empty object if not defined |
| `models` | Available models; replaces the complete inherited list. | From the included catalog |

## Credentials

Choose one API key source. Setting a source replaces the inherited source; do not set several in the same entry.

| Field | Description | Default |
| --- | --- | --- |
| `api_key_file` | Path to a private file containing only the API key. | Inherited key source |
| `api_key_env` | Environment variable containing the API key. | Inherited key source |
| `api_key` | Literal API key; prefer a file or environment variable. | Inherited key source |

For example, configure MiniMax with a key file:

```json
{
  "providers": {
    "minimax": {
      "api_key_file": "~/.skiller/secrets/minimax_api_key"
    }
  }
}
```

To configure credentials interactively, see [Add an LLM provider](/docs/getting-started/add-an-llm-provider/).

## Models

Each model entry declares its identifier and token limits. Defining models replaces the entire provider model list.

| Field | Description | Default |
| --- | --- | --- |
| `model` | Model identifier accepted by the provider. | Required for each model entry |
| `context_window_tokens` | Positive context window size in tokens. | Required for each model entry |
| `max_output_tokens` | Positive output token limit, sent as max_tokens. | Not set; no explicit limit sent |

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

## Provider options

Use options for body parameters specific to your service. For example, the included MiniMax definition enables reasoning_split:

```json
{
  "providers": {
    "minimax": {
      "options": {
        "reasoning_split": true
      }
    }
  }
}
```

Only use parameters supported by the service. To define a new connection rather than customize a built-in provider, see [Custom LLM providers](/docs/configuration/custom-llm-providers/).
