---
title: Debug settings
description: Debug settings enable diagnostic logs for LLM requests and responses.
---

Debug settings enable diagnostic logs for LLM requests and responses.

## Configure debug

Skiller uses the debug section from the [agent profile](/docs/configuration/agent-profiles/) first. Select the profile in the workflow YAML:

```yaml
- agent: reviewer
  config:
    file: "~/.skiller/profiles/agent.reviewer.json"
```

If the profile has no such section, Skiller uses the settings in `~/.skiller/settings/agent.json`, the [global agent configuration](/docs/configuration/global-agent/). If neither defines it, Skiller uses the defaults below.

The profile replaces the entire section. Omitted fields use their defaults rather than inheriting individual global values.

## Debug section shape

Both files use the same structure:

```json
{
  "debug": {
    "log_request": true,
    "log_streaming": false,
    "log_request_file": null,
    "log_override_file": true
  }
}
```

## Fields

| Field | Description | Default |
| --- | --- | --- |
| `log_request` | Enables request and response logging. | `false` |
| `log_streaming` | Captures streaming events where supported, when request logging is enabled. | `false` |
| `log_request_file` | Log destination; null uses the provider-specific path below. | `null` |
| `log_override_file` | Reuses the destination for each request instead of creating timestamped files. | `true` |

## Log files

Without a custom destination, logs use `~/.skiller/logs/request/<provider>/request.json`. With log_override_file enabled, each new request replaces the previous log. Disable it to keep separate timestamped files.

Streaming capture is implemented by Codex and Bedrock. The OpenAI-compatible adapter does not use log_streaming.

Logs can contain conversation content and tool data. Keep them private and disable request logging when diagnostics are no longer needed. These settings are separate from the Runtime logging level.

## Defaults

These values apply in memory when neither configuration defines the section; Skiller does not create a file with this JSON:

```json
{
  "debug": {
    "log_request": false,
    "log_streaming": false,
    "log_request_file": null,
    "log_override_file": true
  }
}
```
