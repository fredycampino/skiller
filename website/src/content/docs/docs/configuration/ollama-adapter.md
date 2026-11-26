---
title: Ollama adapter
description: Configure local or remote Ollama servers through the native Chat API.
---

Uses the native Ollama Chat API (`/api/chat`), not the OpenAI-compatible endpoint. Supports text responses and tool calls when the selected model supports them.

Built-in provider using this adapter:

- Ollama (`ollama`)

## Override providers

Customize the built-in `ollama` provider by overriding its definition in your [user provider catalog](/docs/configuration/llm-providers/):

```json
{
  "providers": {
    "ollama": {
      "enabled": true,
      "base_url": "http://127.0.0.1:11434",
      "timeout_seconds": 600,
      "keep_alive": "5m",
      "models": [
        {
          "model": "hf.co/unsloth/Qwen3.8-27B-GGUF:UD-Q6_K",
          "context_window_tokens": 32768,
          "max_output_tokens": 4096,
          "effort_mapping": ["low", "low", "medium", "medium", "xhigh"],
          "params": {
            "temperature": 0.8,
            "top_p": 0.9,
            "top_k": 40
          }
        }
      ]
    }
  }
}
```

Include only the fields you want to change, but always include a non-empty `models` list. Omitted provider fields, including `adapter`, are inherited from the built-in catalog definition. The model list replaces the entire inherited list. Replace the example identifier with a model installed on your server; sampling values are illustrative and thinking levels must be supported by that model.

## Define new Ollama-based providers

Use a new provider name and declare `"adapter": "ollama"`, following the definition above:

```json
{
  "providers": {
    "my-ollama": {
      "adapter": "ollama",
      "...": "..."
    }
  }
}
```

`"..."` represents the remaining provider fields from the previous example; it is not a configuration field. This adds a separate connection without changing the built-in provider. Select its name in your [agent configuration](/docs/configuration/model-selection/).

## Provider fields

The defaults below are the values in the built-in `ollama` definition. A new provider must declare its connection, timeout, enabled state, and models explicitly.

| Field | Description | Default |
| --- | --- | --- |
| `enabled` | Makes the provider available. | `true` |
| `base_url` | Ollama server root URL, without `/v1` or `/api/chat`. | `http://127.0.0.1:11434` |
| `timeout_seconds` | Positive request timeout in seconds. | `600` |
| `keep_alive` | How long to keep the model loaded after a request; a duration string or integer seconds. `0` unloads it after the request; a negative value keeps it loaded. | Not sent; uses `OLLAMA_KEEP_ALIVE` if defined; otherwise the Ollama server uses `5m`. |
| `models` | Available models; replaces the complete inherited list. | Required and non-empty in user configuration; the base catalog has no models. |

## Connection

Start an Ollama server and download at least one model before configuring Skiller. The server can run locally or on another machine reachable from Skiller. Installing Skiller installs the Python SDK, not the Ollama server or model weights.

Use [Add an LLM provider](/docs/getting-started/add-an-llm-provider/) or `/auth ollama` in STUI for guided setup. No API key is requested. Setup discovers installed completion models and writes their configuration to your provider catalog.

## Models

Each entry declares an installed model and its token limits. Defining `models` replaces the full inherited list.

| Field | Description | Default |
| --- | --- | --- |
| `model` | Exact, non-empty model identifier installed on the server. | Required for each model entry |
| `context_window_tokens` | Positive context window size, sent as `options.num_ctx`. | Required; guided setup uses the active context when available, otherwise 32,768 tokens. |
| `max_output_tokens` | Positive output token limit, sent as `options.num_predict`. | Not sent; uses the model setting; otherwise the Ollama server uses `-1` (no fixed output-token cap). |
| `params` | Per-model sampling settings, mapped to native `options`. | Not sent |
| `effort_mapping` | Five boolean or non-empty string values mapping agent effort levels 1–5 to native `think`. | Not sent |

## Model parameters

Set sampling parameters inside each model's `params`, not at provider level:

```json
{
  "params": {
    "temperature": 0.8,
    "top_p": 0.9,
    "top_k": 40
  }
}
```

The values above illustrate the configuration shape, not recommended settings for every model. Skiller sends only configured parameters. Omitted parameters use the model's settings, then the Ollama server defaults.

| Field | Description | Default |
| --- | --- | --- |
| `temperature` | Sampling temperature, zero or greater. | Model setting; otherwise the Ollama server uses `0.8`. |
| `top_p` | Nucleus sampling probability, greater than 0 and at most 1. | Model setting; otherwise the Ollama server uses `0.9`. |
| `top_k` | Maximum sampling candidates per token, zero or greater. | Model setting; otherwise the Ollama server uses `40`. |
| `seed` | Integer sampling seed. | Model setting; otherwise the Ollama server uses `-1` (random seed). |
| `repeat_penalty` | Repetition penalty, zero or greater. | Model setting; otherwise the Ollama server uses `1.0`. |
| `stop` | Array of stop sequences. | Model setting; otherwise the Ollama server uses no additional stop sequences. |

## Effort mapping

Configure `effort_mapping` inside a model only with values supported by that model. For a model with boolean thinking controls:

```json
{
  "effort_mapping": [true, true, true, true, true]
}
```

For a model supporting `low`, `medium`, and `high`:

```json
{
  "effort_mapping": ["low", "low", "medium", "high", "high"]
}
```

| `llm.effort` | `effort_mapping` | Native `think` |
| --- | --- | --- |
| Not set | - | Not sent |
| - | Absent | Not sent |
| Set to 1–5 | Present | Value at index `effort - 1`, including explicit `false` |

For the Qwen model configured in the override example, set the agent's `llm` configuration to:

```json
{
  "llm": {
    "provider": "ollama",
    "model": "hf.co/unsloth/Qwen3.8-27B-GGUF:UD-Q6_K",
    "effort": 3
  }
}
```

With `effort_mapping: ["low", "low", "medium", "medium", "xhigh"]`, effort `3` selects the third value and sends `"think": "medium"` to Ollama.

When `think` is omitted, Ollama uses the model's default behavior. Skiller does not infer supported thinking levels from model names.

For agent-level provider, model, and effort selection, see [Model selection](/docs/configuration/model-selection/).
