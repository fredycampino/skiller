---
title: Codex adapter
description: Configure providers that use the Codex Responses integration.
---

Uses the Codex Responses integration with OAuth credentials. This adapter connects to the Codex service, not arbitrary OpenAI Responses endpoints.

## Provider section shape

Add the definition to your [user provider catalog](/docs/configuration/llm-providers/):

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
          "context_window_tokens": 1050000
        }
      ]
    }
  }
}
```

This example defines a separate Codex provider. To customize the built-in codex entry, use that name, omit adapter, and include only the fields you want to change.

## Provider fields

The defaults below are the values in the built-in codex definition. A new provider must declare these fields explicitly.

| Field | Description | Default |
| --- | --- | --- |
| `enabled` | Makes the provider available. | `true` |
| `credentials_file` | Path to the OAuth credentials file. | `~/.skiller/secrets/openai-codex.json` |
| `timeout_seconds` | Positive request timeout in seconds. | `120` |
| `parallel_tool_calls` | Requests parallel tool calls in the general Responses transport; the lite transport disables them. | `true` |
| `models` | Available models; replaces the complete inherited list. | From the included catalog |

## Credentials

Use [Add an LLM provider](/docs/getting-started/add-an-llm-provider/) to authenticate with Codex. Authentication creates the OAuth credentials file; reference it rather than copying its contents into provider configuration.

The credentials file must exist and be valid. Access to a configured model depends on your account.

## Models

| Field | Description | Default |
| --- | --- | --- |
| `model` | Codex model identifier. | Required for each model entry |
| `context_window_tokens` | Positive context window size in tokens. | Required for each model entry |

Defining models replaces the full inherited list. For agent-level provider, model, and effort selection, see [Model selection](/docs/configuration/model-selection/).
