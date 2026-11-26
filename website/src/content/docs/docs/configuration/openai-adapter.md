---
title: OpenAI adapter
description: Configure providers that use the OpenAI-compatible Chat Completions API.
---

Uses the OpenAI-compatible Chat Completions API.

Built-in providers using this adapter:

- MiniMax (`minimax`)
- Moonshot (`moonshot`)
- DeepSeek (`deepseek`)
- OpenRouter (`openrouter`)
- LM Studio (`lmstudio`)

## Override providers

Customize a built-in provider by overriding its definition in your [user provider catalog](/docs/configuration/llm-providers/). Replace `<provider>` with its catalog name, such as `minimax`, `moonshot`, `deepseek`, `openrouter`, or `lmstudio`:

```json
{
  "providers": {
    "<provider>": {
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

Include only the fields you want to change. Omitted fields, including `adapter`, are inherited from the built-in catalog definition. If supplied, `models` replaces the entire inherited list. The URL, credentials, and model above are placeholders: use values supported by your provider.

## Define new OpenAI-based providers

Use a new provider name and declare `"adapter": "openai"`, following the definition above:

```json
{
  "providers": {
    "my-provider": {
      "adapter": "openai",
      "...": "..."
    }
  }
}
```

`"..."` represents the remaining provider fields from the previous example; it is not a configuration field. This adds a separate connection without changing any built-in provider. Select its name in your [agent configuration](/docs/configuration/model-selection/).

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

Only use parameters supported by the service. To add a separate connection, see [Define new OpenAI-based providers](#define-new-openai-based-providers).
