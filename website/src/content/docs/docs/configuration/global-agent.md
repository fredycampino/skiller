---
title: Global agent configuration
description: Set the default model, execution limits, context, and diagnostics for your agents.
---

Global agent configuration provides shared defaults for your agents in `~/.skiller/settings/agent.json`. Authentication saves your provider and model selection here; you can customize the other settings as needed.

## Configuration file

This example selects a model and shows the main configuration blocks. Choose a provider and model available in your [LLM provider catalog](/docs/configuration/llm-providers/).

```json
{
  "llm": {
    "provider": "minimax",
    "model": "MiniMax-M3.1-Flash",
    "effort": 3
  },
  "loop": {
    "max_turns": 30,
    "max_tool_calls": 10
  },
  "context": {
    "compaction": {
      "compaction_trigger_ratio": 0.8,
      "compaction_target_ratio": 0.5,
      "keep_last_blocks": 5
    }
  },
  "tools": {},
  "debug": {
    "log_request": false,
    "log_streaming": false,
    "log_override_file": true
  },
  "event_output": {
    "truncate": {
      "enabled": true,
      "max_text_chars": 600,
      "max_json_chars": 4000,
      "max_array_items": 20
    }
  }
}
```

## llm

Selects the provider and model used by the agent. Connection settings and credentials belong in the provider catalog, not here.

| Field | Description | Default |
| --- | --- | --- |
| `provider` | Provider name in the catalog. | Required |
| `model` | Model identifier declared by that provider. | Required |
| `effort` | Reasoning effort from 1 to 5; support depends on the adapter and model. | Not set |

## loop

Limits execution within an agent step, not the number of messages you can send to a persistent agent.

| Field | Description | Default |
| --- | --- | --- |
| `max_turns` | Maximum model turns in an agent step. | `30` |
| `max_tool_calls` | Maximum tool calls accepted in a single model response. | `10` |

Both values must be positive integers.

## context

Controls the context window and when conversation history is compacted.

| Field | Description | Default |
| --- | --- | --- |
| `window_width_tokens` | Optional positive context cap; cannot exceed the model's declared window. | Model context window |
| `compaction.compaction_trigger_ratio` | Window usage ratio that triggers compaction. | `0.8` |
| `compaction.compaction_target_ratio` | Target usage ratio after compaction; must be lower than the trigger. | `0.5` |
| `compaction.keep_last_blocks` | Recent blocks retained during compaction, from 1 to 100. | `5` |

## tools

Stores configuration and permissions for registered tools. An empty object adds no explicit tool configuration; it does not grant unrestricted access. The workflow declares which tools the agent can call.

| Field | Description | Default |
| --- | --- | --- |
| `tools` | Tool names mapped to their configuration objects. | `{}` |

For a working example with shell permissions, see [Create a custom agent](/docs/demos/custom-agent/).

## debug

Controls LLM request and response diagnostics. Logs may contain conversation content and tool data; keep them private.

| Field | Description | Default |
| --- | --- | --- |
| `log_request` | Enables request and response logging. | `false` |
| `log_streaming` | Includes provider streaming events when request logging is enabled. | `false` |
| `log_request_file` | Destination for request logs. | `~/.skiller/logs/request/<provider>/request.json` |
| `log_override_file` | Overwrites the log destination on each request. | `true` |

## event_output

Limits output previews in runtime events, without changing step results or the agent's context.

| Field | Description | Default |
| --- | --- | --- |
| `truncate.enabled` | Enables event output truncation. | `true` |
| `truncate.max_text_chars` | Maximum text characters in a preview. | `600` |
| `truncate.max_json_chars` | Maximum JSON characters in a preview. | `4000` |
| `truncate.max_array_items` | Maximum array items in a preview. | `20` |

The three size limits must be positive integers.
