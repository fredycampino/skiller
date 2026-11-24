# Ollama LLM adapter

## Request

The adapter receives `OllamaLLMRequest`, which inherits the shared `LLMRequest`
and specializes `model` as `OllamaLLMModelDefinition`. The base model contains only
the identifier and token limits; the Ollama model adds `params` and `effort_mapping`.
The request validates its model at construction, before reaching the mapper.

### Domain request: `LLMRequest`

Defined in `packages/skiller/src/skiller/domain/agent/llm/request.py`:

```python
@dataclass(frozen=True)
class LLMRequest:
    messages: tuple[LLMMessage, ...]
    model: LLMModelLike
    effort: int | None = field(default=None, kw_only=True)
    tools: tuple[ToolDefinition, ...] = field(default=(), kw_only=True)
    response_format: LLMResponseFormat | None = field(default=None, kw_only=True)
    log_request_file: str | None = field(default=None, kw_only=True)
    log_override_file: bool = field(default=True, kw_only=True)
    log_streaming: bool = field(default=False, kw_only=True)
```

| Field | Purpose |
| --- | --- |
| `messages` | Conversation, including assistant tool calls and tool results. |
| `model` | Model identifier, context window and optional output-token limit. |
| `effort` | Optional reasoning effort for this invocation, on the Runtime scale of 1–5. |
| `tools` | Available tool definitions and input schemas. |
| `response_format` | Optional JSON output or JSON Schema constraint. |
| `log_request_file` | Local request/response log destination. Never sent to Ollama. |
| `log_override_file` | Whether the local log is overwritten. Never sent to Ollama. |
| `log_streaming` | Runtime logging setting, not Ollama's `stream` switch. |

Temperature and other sampling parameters are adapter configuration, not fields
of the shared request. Context and output-token limits already travel with
`model`; they must not be duplicated in that configuration.

### Native request: `POST /api/chat`

The following example shows native chat fields relevant to this adapter and a
selection of native model options. Optional fields are shown to explain the
protocol, not as recommended settings to enable together. Model support varies,
particularly for reasoning and log probabilities.

```json
{
  "model": "hf.co/unsloth/Qwen3.8-27B-GGUF:UD-Q6_K",
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful assistant."
    },
    {
      "role": "user",
      "content": "What is the current weather in Madrid?"
    }
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_weather",
        "description": "Returns the current weather for a city.",
        "parameters": {
          "type": "object",
          "properties": {
            "city": { "type": "string" }
          },
          "required": ["city"]
        }
      }
    }
  ],
  "format": {
    "type": "object",
    "properties": {
      "city": { "type": "string" },
      "temperature_c": { "type": "number" },
      "condition": { "type": "string" }
    },
    "required": ["city", "temperature_c", "condition"],
    "additionalProperties": false
  },
  "options": {
    "num_ctx": 32768,
    "num_predict": 1024,
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "seed": 42,
    "repeat_penalty": 1.1,
    "stop": ["<END>"]
  },
  "think": true,
  "stream": false,
  "keep_alive": "5m"
}
```

`format` is derived exclusively from `request.response_format`: `JSON_SCHEMA`
sends the schema object directly, as shown above; `JSON_OBJECT` sends `"json"`;
`None` omits the field. It is not adapter configuration.

Messages may additionally carry
`images`, `thinking`, `tool_calls` or `tool_name`, depending on their role and
model capabilities. The `options` object supports additional inference settings;
it is not limited to the examples above.

### Mapping boundary and current implementation

| Native field | Source | Current implementation |
| --- | --- | --- |
| `model` | `request.model.value` | Mapped. |
| `messages` | `request.messages` | Text, tool calls and tool results mapped. |
| `tools` | `request.tools` | Mapped when non-empty. |
| `format` | `request.response_format` | JSON object or JSON Schema mapped. |
| `options.num_ctx` | `request.model.model_context_window_tokens` | Mapped. |
| `options.num_predict` | `request.model.max_output_tokens` | Mapped when present. |
| Other `options` | Model configuration: `params` | Mapped from `request.model.params`; unset values are omitted. |
| `think` | Translation of `request.effort` and model reasoning configuration | Mapped through `request.model.effort_mapping` when both effort and mapping exist. |
| `stream` | Adapter transport mode | Fixed to `false`; streaming is not implemented. |
| `keep_alive` | Ollama adapter configuration | Injected into the mapper; sent when not `None`. |
| `logprobs` | Out of scope | Not supported; not sent. |
| `top_logprobs` | Out of scope | Not supported; not sent. |

### Provider and model configuration

The following JSON describes the supported provider configuration shape. Catalog
parsing, native request mapping and resolver wiring are implemented.

```json
{
  "providers": {
    "ollama": {
      "adapter": "ollama",
      "enabled": true,
      "base_url": "http://192.168.1.202:11434",
      "timeout_seconds": 600,
      "keep_alive": "5m",
      "models": [
        {
          "model": "hf.co/unsloth/Qwen3.8-27B-GGUF:UD-Q6_K",
          "context_window_tokens": 32768,
          "max_output_tokens": 1024,
          "effort_mapping": ["low", "low", "medium", "medium", "xhigh"],
          "params": {
            "temperature": 1,
            "top_p": 0.95,
            "top_k": 40,
            "seed": 42,
            "repeat_penalty": 1.1,
            "stop": ["<END>"]
          }
        }
      ]
    }
  }
}
```

#### Configuration fields and defaults

This table describes the catalog configuration contract. Required fields must
be resolved before constructing the adapter.
Example values above are not implicit defaults.

| Configuration field | Required | Behavior when omitted / default |
| --- | --- | --- |
| `adapter` | Yes, in a complete provider definition | `ollama`; an override may inherit it from the base catalog. |
| `enabled` | No | `true`, following the provider catalog convention. |
| `base_url` | Yes, in the resolved provider | No new default defined here; use the configured URL. Local example: `http://127.0.0.1:11434`. |
| `timeout_seconds` | Yes, in the resolved provider | No new default defined here; use the configured timeout. |
| `keep_alive` | No | Omit from the native request; use `OLLAMA_KEEP_ALIVE` if defined; otherwise the Ollama server uses `5m` (5 minutes). |
| `models` | Yes | At least one model definition. |
| `models[].model` | Yes | No default; exact installed model identifier. |
| `models[].context_window_tokens` | Yes | No mapper fallback; sent as `options.num_ctx`. The auth flow's separate discovery fallback is 32,768. |
| `models[].max_output_tokens` | No | Omit `num_predict`; use the model setting; otherwise the Ollama server uses `-1` (no fixed output-token cap). |
| `models[].effort_mapping` | No | Omit `think` when absent. When configured, exactly five boolean or string values map effort levels 1–5. |
| `models[].params` | No | No sampling overrides; preserve the model/server settings. |
| `params.temperature` | No | Model setting; otherwise the Ollama server uses `0.8`. |
| `params.top_p` | No | Model setting; otherwise the Ollama server uses `0.9`. |
| `params.top_k` | No | Model setting; otherwise the Ollama server uses `40`. |
| `params.seed` | No | Model setting; otherwise the Ollama server uses `-1` (random seed). |
| `params.repeat_penalty` | No | Model setting; otherwise the Ollama server uses `1.0` (no repetition penalty). |
| `params.stop` | No | Model stop sequences; otherwise the Ollama server uses no additional stop sequences. |

### Effort mapping

Reasoning uses `request.effort` and the model's optional `effort_mapping`.
The array contains exactly five boolean or string values, one for each effort
level from 1 to 5. Values must match the controls supported by that model.

| Request effort | Model `effort_mapping` | Native `think` |
| --- | --- | --- |
| Absent (`None`) | Present or absent | Omitted. |
| Present (1–5) | Absent | Omitted. |
| Present (1–5) | Present | Send `effort_mapping[effort - 1]`, including explicit `false`. |

For boolean controls, an example mapping is `[true, true, true, true, true]`.
For Qwen3.8 levels, an example is `["low", "low", "medium", "medium", "xhigh"]`.
Omitting `think` leaves the thinking behavior to Ollama and the model.
This mapping replaces the previously proposed model boolean flag.

The catalog preserves `effort_mapping` and the native request mapper applies
this rule. Effort must be an integer from 1 to 5.

Protocol references: [Ollama chat API](https://docs.ollama.com/api/chat) and
[official Python SDK types](https://github.com/ollama/ollama-python/blob/main/ollama/_types.py).

## Runtime integration and onboarding

The default catalog selects the native `ollama` adapter. The prompt builder
uses `OllamaLLMRequest`; the model manager and client resolver route it to
`OllamaLLMPort`, injecting the provider timeout, URL and `keep_alive`.

`auths/ollama` offers a local connection at `http://127.0.0.1:11434` or a custom
URL without requesting an API key. A trailing `/v1` from an existing URL is
removed by onboarding and by the native transport boundary. Discovery uses
`/api/tags`, `/api/ps` and `/api/show`, excludes non-completion models, selects a
loaded model first and uses its active context or a 32,768-token fallback.
Existing per-model parameters and effort mappings are preserved for models
still installed. Configuration is backed up before writing; the verification
agent uses the native adapter and failed validation restores the backup.

The provider E2E is `packages/skiller/tests/e2e-provider/ollama_tool_usage.sh`.
Enable it with `RUN_OLLAMA_PROVIDER_E2E=1`; configure `OLLAMA_BASE_URL` and,
optionally, `OLLAMA_MODEL` and `SKILLER_RUNTIME_PYTHON`. It uses temporary settings,
loads the real catalog and requests a tool call without executing the tool.
It does not install models or start services.

### Interrupted setup and backup ownership

Configuration operations receive `--run-id` from `flow.run_id`. An exclusive
file lock serializes backup, configure, commit and restore. A pending directory
in the settings directory retains the owner run ID and backups between steps;
a second backup attempt never replaces it, even for the same run.
Only the owner may configure, commit or restore. Existing legacy backups also
block setup rather than being overwritten.

After an interrupted run, restore its original settings with
`ollama_auth.py restore --run-id <owner-run-id>` using the Runtime Python and
the helper path. The pending-operation error identifies that owner. Do not
restore while the owning run is still executing. No automatic recovery is
performed when a different run starts.
