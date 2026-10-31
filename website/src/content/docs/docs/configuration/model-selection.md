---
title: Model selection
description: Choose the provider, model, and reasoning effort for your agents.
---

Model selection defines which LLM an agent uses. Choose a provider and model from your [provider catalog](/docs/configuration/llm-providers/); connection settings and credentials belong in that catalog.

## Configure agent model

Skiller uses the LLM section from the agent profile first (see [Agent profiles](/docs/configuration/agent-profiles/)). This is the file selected in the workflow YAML:

```yaml
- agent: reviewer
  config:
    file: "~/.skiller/profiles/agent.reviewer.json"
```

If the profile has no LLM section, Skiller uses the settings in `~/.skiller/settings/agent.json`, the [global agent configuration](/docs/configuration/global-agent/).

If neither file defines it, configuration validation fails: an agent requires a provider and model.

## LLM section shape

Both files use the same structure:

```json
{
  "llm": {
    "provider": "bedrock",
    "model": "us.anthropic.claude-opus-4-6-v1",
    "effort": 3
  }
}
```

Adding the LLM section to a profile replaces the entire global section. Both provider and model must be present; omitted effort is left unset rather than inherited.

## Fields

| Field | Description | Default |
| --- | --- | --- |
| `provider` | Provider name in the catalog. | Required; no default |
| `model` | Model identifier declared by that provider. | Required; no default |
| `effort` | Reasoning effort from 1 to 5; support depends on the adapter and model. | Not set |

## Defaults

Skiller does not select a provider or model automatically when the LLM section is missing. Authentication saves a selection in the global agent configuration, which profiles can inherit.

Effort is optional. Leaving it unset does not guarantee that reasoning is disabled: adapter and model behavior determines how the request is handled.

## Model effort

Effort requests a reasoning level from 1 to 5. Its meaning depends on the adapter, provider, and model. Skiller's mappers translate the level into the corresponding API setting and apply model-specific adjustments where implemented to find the closest supported match. This is not automatic negotiation: not every model supports every level.

Higher effort requests more reasoning; it is not an output token limit or a guarantee of better results.

| Effort | Base mapping |
| --- | --- |
| 1 | low |
| 2 | medium |
| 3 | high |
| 4 | xhigh |
| 5 | max |

### OpenAI-compatible adapter

Sends the mapped level as the API's reasoning effort. Support depends on the provider and model; Skiller does not retry with a lower level if it is rejected. When effort is omitted, the parameter is not sent and the provider applies its own behavior.

### Bedrock adapter

Applies effort to Anthropic models using adaptive thinking. Other Bedrock models ignore this setting.

The mapper adjusts specific model limitations: for Opus 4.6 and Sonnet 4.6, level 4 maps to high rather than xhigh. In the example above, level 3 requests high effort for Opus 4.6.

Without effort, the mapper requests disabled thinking, except for models it identifies as adaptive-only, where it requests adaptive thinking with medium effort.

### Codex adapter

The configured effort is not applied. Both Codex transports currently send a fixed medium effort, whether or not the LLM section includes this field.
