# Agent LLM Usage

## Current domain object

The current domain object is the frozen `LLMUsage` dataclass defined in
`skiller.domain.agent.llm.model`:

```python
@dataclass(frozen=True)
class LLMUsage:
    prompt_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    cache_read_tokens: int | None
    cache_write_tokens: int | None
    provider: AgentLLMProviderType | None
    model: str | None
```

Every constructor argument is required, while the value may still be `None`
when an LLM provider omits that part of the usage information. The object is
immutable after construction.

### Fields

| Field | Meaning in the current implementation |
| --- | --- |
| `prompt_tokens` | Input/prompt token count reported by the provider. OpenAI maps `usage.prompt_tokens`, Codex maps `usage.input_tokens`, and Bedrock maps `usage.inputTokens` directly. Skiller does not currently adjust this value for prompt-cache reads or writes. |
| `output_tokens` | Generated/output token count reported by the provider. OpenAI maps `usage.completion_tokens`, Codex maps `usage.output_tokens`, and Bedrock maps `usage.outputTokens`. |
| `total_tokens` | Total token count reported by the provider. OpenAI and Codex map `usage.total_tokens`; Bedrock maps `usage.totalTokens`. Skiller does not recalculate this value. |
| `cache_read_tokens` | Prompt tokens read from provider cache. OpenAI maps `prompt_tokens_details.cached_tokens`, Codex maps `input_tokens_details.cached_tokens`, and Bedrock maps `cacheReadInputTokens`. |
| `cache_write_tokens` | Prompt tokens written to provider cache. OpenAI maps `prompt_tokens_details.cache_write_tokens`, Codex maps `input_tokens_details.cache_write_tokens`, and Bedrock maps `cacheWriteInputTokens`. |
| `provider` | The Skiller LLM provider associated with the response, when available. `LLMUsage.__post_init__` normalizes it to `AgentLLMProviderType`. |
| `model` | The model identifier associated with the response, when available. It must be a non-empty string or an `LLMModelLike` value and is stored as a string. |

## Provider mapping

The infrastructure mappers convert provider-specific usage objects into the
same domain object:

| Provider/API | Provider field | Domain field |
| --- | --- | --- |
| OpenAI Chat Completions | `prompt_tokens` | `prompt_tokens` |
| OpenAI Chat Completions | `completion_tokens` | `output_tokens` |
| OpenAI Chat Completions | `total_tokens` | `total_tokens` |
| Codex Responses | `input_tokens` | `prompt_tokens` |
| Codex Responses | `output_tokens` | `output_tokens` |
| Codex Responses | `total_tokens` | `total_tokens` |
| Bedrock Converse | `inputTokens` | `prompt_tokens` |
| Bedrock Converse | `outputTokens` | `output_tokens` |
| Bedrock Converse | `totalTokens` | `total_tokens` |

The current mappers populate the three token-count fields and the two cache
counters when the provider reports them. The provider and model metadata may be
added by the surrounding response or application mapping flow.

## Persistence and usage

When usage is persisted in agent context, it is serialized as JSON with the
following current shape:

```json
{
  "prompt_tokens": 3010,
  "output_tokens": 231,
  "total_tokens": 3241,
  "cache_read_tokens": 2560,
  "cache_write_tokens": null,
  "provider": "openai",
  "model": "gpt-4.1"
}
```

`provider` and `model` are omitted when they are `None`. The persisted usage is
attached to the corresponding `AgentContextEntry` and is available for the
latest assistant response and context statistics.

The context publisher uses `prompt_tokens` to calculate the token delta between
comparable usage markers. If the value is missing, decreases unexpectedly, or
the context window has moved or been rebased, Skiller estimates the delta from
the current context payload instead.

## Current limitations

Cache detail arrays such as Bedrock `cacheDetails` are not normalized into the
domain object. Only cache read and cache write token counters are persisted.
Reasoning-token metrics are intentionally outside the current contract.
