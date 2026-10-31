---
title: Event output
description: Event output settings control the size of agent message and tool previews in runtime events.
---

Event output settings control the size of agent message and tool previews in runtime events.

## Configure event output

Skiller uses the event output section from the [agent profile](/docs/configuration/agent-profiles/) first. Select the profile in the workflow YAML:

```yaml
- agent: reviewer
  config:
    file: "~/.skiller/profiles/agent.reviewer.json"
```

If the profile has no such section, Skiller uses the settings in `~/.skiller/settings/agent.json`, the [global agent configuration](/docs/configuration/global-agent/). If neither defines it, Skiller uses the defaults below.

The profile replaces the entire section. Omitted fields use their defaults rather than inheriting individual global values.

## Event output section shape

Both files use the same structure:

```json
{
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

## Fields

| Field | Description | Default |
| --- | --- | --- |
| `truncate.enabled` | Enables truncation of event previews. | `true` |
| `truncate.max_text_chars` | Maximum text characters in a preview. | `600` |
| `truncate.max_json_chars` | Character limit used for JSON previews. | `4000` |
| `truncate.max_array_items` | Maximum array items retained in a preview. | `20` |

## What truncation affects

These limits shorten event previews, not the agent's conversation context or the underlying step results. They are not a context-window or tool-result budget.

All three size limits must be positive integers. Set truncate.enabled to false to disable preview truncation; events may then contain much larger payloads.

## Defaults

These values apply in memory when neither configuration defines the section; Skiller does not create a file with this JSON:

```json
{
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
