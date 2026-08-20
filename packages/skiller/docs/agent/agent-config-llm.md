# LLM Configuration

This document describes the provider catalog used by the agent runtime. The
catalog is stored in `providers.json` and contains the provider definitions,
adapter-specific settings, credentials references, and supported models.

```json
{
  "providers": {
    "provider-name": {
      "adapter": "openai",
      "enabled": true,
      "base_url": "https://provider.example/v1",
      "api_key_env": "PROVIDER_API_KEY",
      "timeout_seconds": 30,
      "temperature": 1,
      "top_p": 1,
      "max_output_tokens": 4096,
      "parallel_tool_calls": true,
      "tool_choice": "auto",
      "models": [
        {
          "model": "provider-model",
          "context_window_tokens": 128000
        }
      ]
    }
  }
}
```

To create a provider, add an entry under `providers` using a unique provider
name, choose a supported `adapter`, provide the fields required by that
adapter, and declare every supported model in `models`. Each model entry must
include its provider model identifier and context window.

For example, an OpenAI-compatible provider can be added as follows:

```json
{
  "providers": {
    "minimax": {
      "adapter": "openai",
      "enabled": true,
      "base_url": "https://api.minimax.io/v1",
      "api_key_env": "AGENT_MINIMAX_API_KEY",
      "timeout_seconds": 30,
      "temperature": 1,
      "top_p": 1,
      "max_output_tokens": 4096,
      "parallel_tool_calls": true,
      "tool_choice": "auto",
      "models": [
        {
          "model": "MiniMax-M3",
          "context_window_tokens": 204800
        }
      ]
    }
  }
}
```

The agent selects this entry separately in `agent.json` with
`llm.provider = "minimax"` and `llm.model = "MiniMax-M3"`. Provider
definitions and credentials references must not be placed in `agent.json`.

## Common provider JSON contract

All providers use the same top-level structure. Providers are indexed by name
to make lookup and merge operations deterministic:

```json
{
  "providers": {
    "provider-name": {
      "adapter": "adapter-name",
      "enabled": true,
      "timeout_seconds": 30,
      "max_output_tokens": 4096,
      "models": [
        {
          "model": "provider-model",
          "context_window_tokens": 128000
        }
      ]
    }
  }
}
```

### Common required fields

| Field | Type | Description |
|---|---|---|
| `adapter` | `string` | Registered adapter used to create the client. |
| `enabled` | `boolean` | Enables or disables the provider. |
| `timeout_seconds` | `number` | Request timeout. Must be greater than zero. |
| `max_output_tokens` | `integer` | Maximum output tokens. Must be greater than zero. |
| `models` | `array` | Models supported by the provider. Must not be empty. |
| `models[].model` | `string` | Model identifier sent to the provider. |
| `models[].context_window_tokens` | `integer` | Model context window. Must be greater than zero. |

Each model defines its context window:

```json
{
  "model": "provider-model",
  "context_window_tokens": 128000
}
```

Generation parameters, authentication, endpoints, and other runtime options
are adapter-specific. They are documented in the corresponding adapter
section and must not be assumed to be available for every provider.

## Built-in application catalog

The application ships with a default catalog named `providers.json`:

```text
packages/skiller/src/skiller/application/config/providers.json
```

This file is part of the application package and is used as the base
configuration for all providers. It must contain provider defaults and
supported models, but must not contain secrets or user-specific paths.

The built-in catalog defines:

- the provider name;
- the adapter name;
- default endpoint or connection settings required by the adapter;
- supported models and their context windows;
- adapter-specific defaults.

It is loaded before user configuration files. User configuration may override
the built-in catalog according to the general merge policy.

Minimal example:

```json
{
  "providers": {
    "minimax": {
      "adapter": "openai",
      "enabled": true,
      "base_url": "https://api.minimax.io/v1",
      "api_key_env": "AGENT_MINIMAX_API_KEY",
      "timeout_seconds": 30,
      "temperature": 1,
      "top_p": 1,
      "max_output_tokens": 4096,
      "parallel_tool_calls": true,
      "tool_choice": "auto",
      "models": [
        {
          "model": "MiniMax-M2.7",
          "context_window_tokens": 204800
        }
      ]
    },
    "bedrock": {
      "adapter": "bedrock",
      "enabled": true,
      "profile": "default",
      "timeout_seconds": 45,
      "max_output_tokens": 4096,
      "models": [
        {
          "model": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
          "context_window_tokens": 200000
        }
      ]
    }
  }
}
```

## Provider configuration files and merge policy

This configuration file and merge policy applies to every provider and
adapter.

The provider catalog is resolved from these files:

```text
application providers.json
    < ~/.skiller/settings/providers.json
    < file specified by AGENT_PROVIDERS_FILE
```

The application file is the built-in default catalog. The user file is an
optional override. `AGENT_PROVIDERS_FILE` is also optional and can point to a
custom, highest-priority override file:

```text
AGENT_PROVIDERS_FILE=/path/to/providers.json
```

Only `AGENT_PROVIDERS_FILE` selects the provider configuration file. Individual
provider fields are not overridden through separate environment variables.

General merge rules:

- Providers are identified by their map key, for example `minimax`.
- A provider defined only in the application file is kept unchanged.
- An existing provider defined in multiple files is merged field by field.
- Values from the higher-priority file override lower-priority values.
- Unspecified fields keep their lower-priority values.
- When a higher-priority file defines `models`, the complete model list is replaced.
- A provider can be disabled explicitly with `"enabled": false`.
- An override of an existing provider must not declare `adapter`; its adapter is fixed by the
  application catalog and only fields supported by that adapter are accepted.
- A provider that is absent from the application catalog is added when the higher-priority file
  declares a registered `adapter` and every field required by that adapter.
- Application defaults must not contain secret values or user-specific credential paths.

When the catalog is exposed through the agent model commands, each provider is
reported with its effective catalog source:

- `default`: application `providers.json`;
- `user`: `~/.skiller/settings/providers.json`;
- `env`: the file selected by `AGENT_PROVIDERS_FILE`.

If a provider is present in more than one file, its source is the highest-
priority file that defines it.

## `openai` adapter

The `openai` adapter is used for providers compatible with the
`chat.completions` API, such as MiniMax, Moonshot, OpenRouter, and LM Studio.

Each provider configuration uses a flat structure:

```json
{
  "adapter": "openai",
  "enabled": true,
  "base_url": "https://provider.example/v1",
  "api_key_env": "PROVIDER_API_KEY",
  "timeout_seconds": 30,
  "temperature": 1,
  "top_p": 1,
  "max_output_tokens": 4096,
  "parallel_tool_calls": true,
  "tool_choice": "auto",
  "models": [
    {
      "model": "provider-model",
      "context_window_tokens": 128000
    }
  ]
}
```

The top-level structure is indexed by provider name so providers can be
merged deterministically:

```json
{
  "providers": {
    "minimax": {
      "adapter": "openai",
      "enabled": true,
      "base_url": "https://api.minimax.io/v1",
      "api_key_file": "~/.skiller/secrets/minimax_api_key",
      "timeout_seconds": 30,
      "temperature": 1,
      "top_p": 1,
      "max_output_tokens": 4096,
      "parallel_tool_calls": true,
      "tool_choice": "auto",
      "models": [
        {
          "model": "MiniMax-M2.5",
          "context_window_tokens": 204800
        }
      ]
    }
  }
}
```

Example user override:

```json
{
  "providers": {
    "minimax": {
      "timeout_seconds": 60,
      "models": [
        {
          "model": "MiniMax-M2.7",
          "context_window_tokens": 204800
        }
      ]
    },
    "custom": {
      "adapter": "openai",
      "enabled": true,
      "base_url": "http://127.0.0.1:1234/v1",
      "api_key_env": "CUSTOM_PROVIDER_API_KEY",
      "timeout_seconds": 30,
      "temperature": 0.2,
      "top_p": 1,
      "max_output_tokens": 4096,
      "parallel_tool_calls": true,
      "tool_choice": "auto",
      "models": [
        {
          "model": "google/gemma-4-12b-qat",
          "context_window_tokens": 131072
        }
      ]
    }
  }
}
```

In this example, MiniMax keeps its application defaults except for
`timeout_seconds` and `models`. `custom` is a new provider, so it declares its
adapter and its complete OpenAI configuration.

### Required fields

| Field | Type | Description |
|---|---|---|
| `adapter` | `string` | Must be `openai`. |
| `enabled` | `boolean` | Enables or disables the provider. |
| `base_url` | `string` | API base URL. Must not be empty. |
| `models` | `array` | Models supported by the provider. Must not be empty. |
| `models[].model` | `string` | Identifier sent to the API. |
| `models[].context_window_tokens` | `integer` | Model context window. Must be greater than zero. |
| `timeout_seconds` | `number` | Request timeout. Must be greater than zero. |
| `temperature` | `number` | Randomness control. Must not be negative. |
| `top_p` | `number` | Cumulative probability sampling. Greater than zero and at most one. |
| `max_output_tokens` | `integer` | Maximum output tokens. Must be greater than zero. |
| `parallel_tool_calls` | `boolean` | Enables parallel tool calls. |
| `tool_choice` | `string` | Values: `auto`, `none`, or `required`. |

An `openai` provider definition requires exactly one of the following
authentication fields:

| Field | Type | Description |
|---|---|---|
| `api_key` | `string` | Key written directly in the configuration. Not recommended. |
| `api_key_env` | `string` | Name of the environment variable containing the key. |
| `api_key_file` | `string` | Path to the file containing the key. Recommended. |

These fields are provider authentication settings. A partial override may
replace the configured source with exactly one of them. The application default
configuration must not contain a secret value or a user-specific credential
path.

### Optional fields

| Field | Type | Default | Description |
|---|---|---|---|
| `options` | `object` | `{}` | Additional provider-specific options. |

## Example: MiniMax

```json
{
  "adapter": "openai",
  "enabled": true,
  "base_url": "https://api.minimax.io/v1",
  "api_key_file": "~/.skiller/secrets/minimax_api_key",
  "timeout_seconds": 30,
  "temperature": 1,
  "top_p": 1,
  "max_output_tokens": 4096,
  "parallel_tool_calls": true,
  "tool_choice": "auto",
  "options": {
    "reasoning_split": true
  },
  "models": [
    {
      "model": "MiniMax-M2.5",
      "context_window_tokens": 204800
    },
    {
      "model": "MiniMax-M2.7",
      "context_window_tokens": 204800
    }
  ]
}
```

## `bedrock` adapter

The `bedrock` adapter uses an AWS profile and Bedrock model identifiers. It
does not use the OpenAI authentication fields.

```json
{
  "adapter": "bedrock",
  "enabled": true,
  "profile": "claude-bedrock",
  "timeout_seconds": 45,
  "max_output_tokens": 4096,
  "models": [
    {
      "model": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
      "context_window_tokens": 200000
    }
  ]
}
```

### Required fields

| Field | Type | Description |
|---|---|---|
| `adapter` | `string` | Must be `bedrock`. |
| `enabled` | `boolean` | Enables or disables the provider. |
| `profile` | `string` | AWS profile used to create the Bedrock session. |
| `timeout_seconds` | `number` | Request timeout. Must be greater than zero. |
| `max_output_tokens` | `integer` | Maximum output tokens. Must be greater than zero. |
| `models` | `array` | Bedrock models supported by the provider. Must not be empty. |
| `models[].model` | `string` | Bedrock model or inference profile identifier. |
| `models[].context_window_tokens` | `integer` | Model context window. Must be greater than zero. |

The selected model must be one of the models declared in `models`. The
application uses the configured AWS profile to create the Bedrock session and
then sends requests using the selected model identifier.

## `codex` adapter

The `codex` adapter uses OpenAI Codex OAuth credentials and the Codex responses
protocol. It does not use the `openai` adapter or its API key fields.

```json
{
  "adapter": "codex",
  "enabled": true,
  "credentials_file": "~/.skiller/secrets/openai-codex.json",
  "timeout_seconds": 120,
  "max_output_tokens": 4096,
  "parallel_tool_calls": true,
  "models": [
    {
      "model": "gpt-5.4",
      "context_window_tokens": 1050000
    },
    {
      "model": "gpt-5.5",
      "context_window_tokens": 1050000
    },
    {
      "model": "gpt-5.6-sol",
      "context_window_tokens": 1050000
    },
    {
      "model": "gpt-5.6-terra",
      "context_window_tokens": 1050000
    },
    {
      "model": "gpt-5.6-luna",
      "context_window_tokens": 1050000
    }
  ]
}
```

### Required fields

| Field | Type | Description |
|---|---|---|
| `adapter` | `string` | Must be `codex`. |
| `enabled` | `boolean` | Enables or disables the provider. |
| `credentials_file` | `string` | Path to the Codex OAuth credentials JSON file. Supports `~`. |
| `timeout_seconds` | `number` | Request timeout. Must be greater than zero. |
| `max_output_tokens` | `integer` | Maximum output tokens. Must be greater than zero. |
| `models` | `array` | Codex models supported by the provider. Must not be empty. |
| `models[].model` | `string` | Codex model identifier. |
| `models[].context_window_tokens` | `integer` | Model context window. Must be greater than zero. |
| `parallel_tool_calls` | `boolean` | Enables parallel tool calls. |

The credentials file contains OAuth state managed by the Codex authentication
flow. Provider configuration stores only its path and must not embed access or
refresh tokens. The adapter refreshes expired credentials through the existing
Codex credentials datasource.

The selected model must be one of the models declared in `models`. Runtime
session identifiers are generated from the agent context and are not provider
configuration fields.
