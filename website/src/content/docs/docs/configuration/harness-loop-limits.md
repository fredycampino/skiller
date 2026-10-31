---
title: Harness loop limits
description: Limit model turns and tool calls within an agent execution.
---

Harness loop limits control how much work an agent can perform during one agent step execution. They do not limit the number of messages you can send to a persistent agent or the number of times a workflow repeats.

## Configure loop limits

Skiller uses the loop section from the [agent profile](/docs/configuration/agent-profiles/) first. Select the profile in the workflow YAML:

```yaml
- agent: reviewer
  config:
    file: "~/.skiller/profiles/agent.reviewer.json"
```

If the profile has no loop section, Skiller uses the settings in `~/.skiller/settings/agent.json`, the [global agent configuration](/docs/configuration/global-agent/). If neither defines it, Skiller uses the defaults below.

A profile's loop section replaces the entire global section. Omitted fields use their defaults, not the corresponding global values.

## Loop section shape

Both files use the same structure:

```json
{
  "loop": {
    "max_turns": 30,
    "max_tool_calls": 10
  }
}
```

## Fields

| Field | Description | Default |
| --- | --- | --- |
| `max_turns` | Maximum model turns during one agent step execution. A turn is one model response, not one tool call. | `30` |
| `max_tool_calls` | Maximum tool calls accepted in a single model response, not a total across the execution. | `10` |

Both values must be positive integers. A model can request several tools in one turn; their results are available to the model on its next turn.

## When a limit is reached

### Model turns

When tools are enabled, the harness warns the model before its last allowed turn. If the budget is exhausted without a final answer, execution stops with the reason `max_turns_exhausted`. The harness records a control message and event, rather than inventing a final answer or treating exhaustion as a technical failure.

The budget starts again on the next agent step execution.

### Tool calls per response

With a limit of 10, a response containing 11 calls is rejected as a whole: none of those tools execute. The harness adds corrective feedback asking the model to return fewer calls and continues if turns remain. The rejected response still consumes a turn.

Ten calls in one response and another ten in a later response are allowed. This setting limits batch size, not the total number of calls or their execution time.

## Step overrides

An agent step can override either limit directly:

```yaml
- agent: reviewer
  config:
    file: "~/.skiller/profiles/agent.reviewer.json"
  max_turns: 15
  max_tool_calls: 3
```

These step values take precedence over the resolved configuration. Runtime also supports environment overrides through `AGENT_LOOP_MAX_TURNS` and `AGENT_LOOP_MAX_TOOL_CALLS`; they apply before step overrides.

## Defaults

When neither configuration defines a loop section, Skiller applies the following values in memory; it does not create a file with this JSON:

```json
{
  "loop": {
    "max_turns": 30,
    "max_tool_calls": 10
  }
}
```
