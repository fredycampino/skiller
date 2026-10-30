---
title: Custom LLM providers
description: Connect a custom LLM service using a supported adapter.
---

Customize providers to connect another LLM service, use separate credentials, or choose the models and token limits available to your agents.

Add these definitions to `~/.skiller/settings/providers.json` or the file selected by `AGENT_PROVIDERS_FILE`. Each new provider has its own name and declares a supported adapter.

## Custom OpenAI-compatible provider

Connect a service that supports the OpenAI Chat Completions API:

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

Replace the example endpoint, model, and token limits with values supported by your service. Make `MY_PROVIDER_API_KEY` available to the Skiller process.

| Field | Description | Default |
| --- | --- | --- |
| `adapter` | Transport implementation: `openai`, `codex`, or `bedrock`. | Required for a new provider |
| `base_url` | API endpoint for the `openai` adapter. | Required for a new OpenAI-compatible provider |
| `temperature` | Sampling temperature. | Required for a new OpenAI-compatible provider |
| `top_p` | Nucleus sampling probability, greater than 0 and at most 1. | Required for a new OpenAI-compatible provider |
| `parallel_tool_calls` | Whether to request parallel tool calls. | Required for a new OpenAI-compatible provider |
| `tool_choice` | Tool selection mode: `auto`, `required`, or `none`. | Required for a new OpenAI-compatible provider |
| `options` | Provider-specific request body parameters, sent as `extra_body`. | `{}` |

Use only options supported by your service. For example, MiniMax supports `"options": {"reasoning_split": true}`.

## Custom Codex provider

Define a separate Codex entry with its own model list. Use an existing OAuth credentials file created through [authentication](/docs/getting-started/add-an-llm-provider/):

```json
{
  "providers": {
    "my-codex": {
      "adapter": "codex",
      "enabled": true,
      "credentials_file": "~/.skiller/secrets/openai-codex.json",
      "timeout_seconds": 120,
      "parallel_tool_calls": true,
      "models": [
        {
          "model": "gpt-5.4",
          "context_window_tokens": 1050000,
          "max_output_tokens": 4096
        }
      ]
    }
  }
}
```

The `codex` adapter uses the Codex service, not a custom OpenAI-compatible endpoint. Model access depends on your account.

## Custom Bedrock provider

Use a named AWS profile and a Bedrock model or inference profile available to that profile:

```json
{
  "providers": {
    "my-bedrock": {
      "adapter": "bedrock",
      "enabled": true,
      "profile": "my-aws-profile",
      "timeout_seconds": 45,
      "models": [
        {
          "model": "us.anthropic.claude-opus-4-6-v1",
          "context_window_tokens": 1000000,
          "max_output_tokens": 4096
        }
      ]
    }
  }
}
```

Replace the profile and model with values available in your AWS setup. The named profile must already be configured; this entry does not create AWS credentials or grant model access.

## Select the provider

Select the provider and model in your agent configuration:

```json
{
  "llm": {
    "provider": "my-provider",
    "model": "my-model"
  }
}
```

Existing providers inherit their adapter from the included catalog; an override cannot change it.
