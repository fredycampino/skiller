---
title: Context settings
description: Configure the agent context window and conversation compaction.
---

Context settings control how much conversation history an agent sends to the model and when older history is compacted.

## Configure agent context

Skiller uses the context section from the agent profile first (see [Agent profiles](/docs/configuration/agent-profiles/)). This is the file selected in the workflow YAML:

```yaml
- agent: reviewer
  config:
    file: "~/.skiller/profiles/agent.reviewer.json"
```

If the profile has no context section, Skiller uses the settings in `~/.skiller/settings/agent.json`, the [global agent configuration](/docs/configuration/global-agent/).

If neither file defines it, Skiller uses the defaults listed below.

## Context section shape

Both files use the same structure:

```json
{
  "context": {
    "window_width_tokens": 200000,
    "compaction": {
      "compaction_trigger_ratio": 0.8,
      "compaction_target_ratio": 0.3,
      "keep_last_blocks": 10
    }
  }
}
```

A profile without `context` inherits the global section. Adding `context` replaces that entire section; omitted fields use schema defaults, not the global values.

## Context window

The effective window is the smaller of `window_width_tokens` and the model context window declared in the [provider catalog](/docs/configuration/llm-providers/). Without a configured cap, Skiller uses the model window.

| Field | Description | Default |
| --- | --- | --- |
| `window_width_tokens` | Positive token cap for the context window. | Model context window |

## Compaction

Before each model request, Skiller checks estimated context usage, including the system prompt. At the trigger threshold, it reduces the history included in subsequent requests; it does not delete the stored conversation or generate an LLM summary.

| Field | Description | Default |
| --- | --- | --- |
| `compaction_trigger_ratio` | Fraction of the effective window that triggers compaction, greater than 0 and at most 1. | `0.8` |
| `compaction_target_ratio` | Target fraction after compaction; must be positive and lower than the trigger. | `0.5` |
| `keep_last_blocks` | Maximum recent complete blocks retained in full within the target budget, from 1 to 100. | `5` |

With the example above and a model window of at least 200,000 tokens, compaction starts at an estimated 160,000 tokens and targets 60,000. The example customizes the target and retained-block count; they are not the defaults.

Recent blocks keep their full tool interactions. Older retained blocks omit tool calls and results while keeping user messages and final agent responses; older blocks that do not fit are left out of the request.

A block is a history segment closed by an assistant response with usage information, not necessarily a whole user task. The open block remains intact, and the latest complete block is kept even if it exceeds the target. The target is therefore not a hard token limit.

## Default context settings

When neither configuration defines a context section, Skiller uses these values in memory; it does not write this JSON to a file:

```json
{
  "context": {
    "window_width_tokens": null,
    "compaction": {
      "compaction_trigger_ratio": 0.8,
      "compaction_target_ratio": 0.5,
      "keep_last_blocks": 5
    }
  }
}
```

A null window cap means the model context window is used.
