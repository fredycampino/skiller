---
title: Codex adapter
description: Configure providers that use the Codex Responses integration.
---

Uses the Codex Responses integration with OAuth credentials. This adapter connects to the Codex service, not arbitrary OpenAI Responses endpoints.

Built-in provider using this adapter:

- OpenAI Codex (`codex`)

## Override providers

Customize the built-in `codex` provider by overriding its definition in your [user provider catalog](/docs/configuration/llm-providers/):

```json
{
  "providers": {
    "codex": {
      "enabled": true,
      "credentials_file": "~/.skiller/secrets/openai-codex.json",
      "timeout_seconds": 600,
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

Include only the fields you want to change. Omitted fields, including `adapter`, are inherited from the built-in catalog definition. If supplied, `models` replaces the entire inherited list. Use model identifiers available to your account.

## Define new Codex-based providers

Use a new provider name and declare `"adapter": "codex"`, following the definition above:

```json
{
  "providers": {
    "my-codex": {
      "adapter": "codex",
      "...": "..."
    }
  }
}
```

`"..."` represents the remaining provider fields from the previous example; it is not a configuration field. This adds a separate connection without changing the built-in provider. Select its name in your [agent configuration](/docs/configuration/model-selection/).

## Provider fields

The defaults below are the values in the built-in codex definition. A new provider must declare these fields explicitly.

| Field | Description | Default |
| --- | --- | --- |
| `enabled` | Makes the provider available. | `true` |
| `credentials_file` | Path to the OAuth credentials file. | `~/.skiller/secrets/openai-codex.json` |
| `timeout_seconds` | Positive request timeout in seconds. | `600` |
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
