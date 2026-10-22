# Thinking effort configuration

```json
{
  "llm": {
    "provider": "bedrock",
    "model": "us.anthropic.claude-opus-4-6-v1",
    "effort": 4
  }
}
```

| `effort` | Bedrock Anthropic mapping |
| --- | --- |
| `1` | `low` |
| `2` | `medium` |
| `3` | `high` |
| `4` | `xhigh` |
| `5` | `max` |

`llm.effort` is optional and accepts only integers from 1 to 5. It travels with
the Runtime LLM request; adapters without effort support ignore it. Currently,
only Bedrock Anthropic maps this setting. Provider catalog entries do not change.

## Bedrock Anthropic rules

- With `effort`: use `adaptive` and map levels 1–5 as above. If unsupported, use the closest supported lower effort level.
- Without `effort`: attempt `disabled`. If the model cannot disable thinking, use `adaptive` with `medium` effort.


## Reference: Anthropic thinking on Amazon Bedrock

Thinking modes and effort enums are listed separately. Their presence in one row
does not establish that every combination is valid when thinking is disabled.
The documented Opus 5 restriction is shown explicitly.

| Model | Non-deprecated `thinking.type` | `output_config.effort` |
| --- | --- | --- |
| Opus 4.6 | `adaptive`, `disabled` | `low`, `medium`, `high`, `max` |
| Opus 4.7 | `adaptive`, `disabled` | `low`, `medium`, `high`, `xhigh`, `max` |
| Opus 4.8 | `adaptive`, `disabled` | `low`, `medium`, `high`, `xhigh`, `max` |
| Opus 5 (adaptive) | `adaptive` | `low`, `medium`, `high`, `xhigh`, `max` |
| Opus 5 (disabled) | `disabled` | `low`, `medium`, `high` |
| Opus 5.5 | `adaptive` only; always on | `low`, `medium`, `high`, `xhigh`, `max` |
| Sonnet 4.6 | `adaptive`, `disabled` | `low`, `medium`, `high`, `max` |
| Sonnet 5 | `adaptive`, `disabled` | `low`, `medium`, `high`, `xhigh`, `max` |
| Fable 5 | `adaptive` only; always on | Complete enum not verified; do not infer it from other models |
| Fable 5.1 | `adaptive` only; always on | `low`, `medium`, `high`, `xhigh`, `max` |
