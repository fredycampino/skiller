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

Selects the provider, model, and optional reasoning effort. See [Model selection](/docs/configuration/model-selection/) for fields, defaults, and global or per-agent examples. Connection settings and credentials belong in the [provider catalog](/docs/configuration/llm-providers/).

## loop

Limits model turns and tool calls per response within an agent step. See [Harness loop limits](/docs/configuration/harness-loop-limits/) for fields, defaults, and what happens when a limit is reached.

## context

Controls the context window and when conversation history is compacted. See [Context settings](/docs/configuration/context-settings/) for fields, defaults, and global or per-agent examples.

## tools

Stores configuration and permissions for registered tools. See [Harness tools](/docs/tools/overview/) for enabling tools and configuring Shell and Files permissions.

## debug

Controls LLM request and response diagnostics. See [Debug settings](/docs/configuration/debug-settings/) for fields, log files, and defaults.

## event_output

Limits previews in runtime events without changing the agent's context. See [Event output](/docs/configuration/event-output/) for fields and defaults.
