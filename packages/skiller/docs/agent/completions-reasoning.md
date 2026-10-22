# Reasoning effort configuration for Chat Completions

```json
{
  "llm": {
    "provider": "minimax",
    "model": "MiniMax-M3.1-Flash",
    "effort": 4
  }
}
```

| `effort` | `reasoning_effort` |
| --- | --- |
| `1` | `low` |
| `2` | `medium` |
| `3` | `high` |
| `4` | `xhigh` |
| `5` | `max` |

`llm.effort` is optional and accepts only integers from 1 to 5. Provider catalog
entries do not change.

## Chat Completions rules

- With `effort`: send the mapped `reasoning_effort` at the request root.
- Without `effort`: omit `reasoning_effort`; the provider/model applies its default.
- Use the same mapping for all providers, without provider-specific fallbacks or extensions. Propagate errors if the model rejects the value.