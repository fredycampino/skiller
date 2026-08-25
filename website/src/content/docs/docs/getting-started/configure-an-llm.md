---
title: Configure an LLM
description: Select the provider and model used by agent steps.
---

The `agent` step requires an effective agent configuration with an LLM provider and model.

Create the user-level file:

```text
~/.skiller/settings/agent.json
```

For example:

```json
{
  "llm": {
    "provider": "minimax",
    "model": "MiniMax-M3"
  }
}
```

Then expose the credential required by that provider:

```bash
export AGENT_MINIMAX_API_KEY="..."
```

Do not commit credentials to a flow, `agent.json`, or the repository.

## Local override

An `agent.json` next to a flow can override the user-level configuration for that flow. Root sections are replaced rather than deeply merged, so an override `llm` section must contain both `provider` and `model`.

## Verify it

Run the [Agent chat](/docs/demos/agent-chat/). Configuration errors are reported before an agent turn is executed.

Provider endpoints, credential variables, model catalog entries, context limits, tools, and loop settings will be added to the configuration reference.
