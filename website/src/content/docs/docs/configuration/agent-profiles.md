---
title: Agent profiles
description: Customize individual agents while keeping shared global defaults.
---

An agent profile overrides selected sections of the [global agent configuration](/docs/configuration/global-agent/). Use profiles to give agents different models, permissions, or execution settings without changing the defaults for everyone.

## Select a profile

Create a JSON file, such as `~/.skiller/settings/agent.reviewer.json`, and reference it in the agent step:

```yaml
- agent: reviewer
  config:
    file: "~/.skiller/settings/agent.reviewer.json"
  system: "Review the submitted text."
  task: "Review this sentence: The service are ready."
```

Relative file paths resolve from the workflow directory. An explicitly selected file must exist; Skiller does not fall back to another profile if it is missing or invalid.

## Inherit the global model

If the profile has no `llm` section, the agent uses the complete global `llm` selection, including `effort` when configured:

```jsonc
{
  // Other profile settings, but no llm section.
}
```

This illustration uses a comment; an empty JSON profile is simply `{}`.

## Choose a different model

Adding `llm` replaces the entire global section:

```json
{
  "llm": {
    "provider": "codex",
    "model": "gpt-5.4"
  }
}
```

Both `provider` and `model` are required in this section. If you omit `effort`, it is left unset rather than inherited. A profile containing only `llm.model` is invalid, even if the global configuration defines a provider.

The same rule applies to other sections: a profile replaces complete root sections, not individual nested fields. Omitted sections keep their global values; omitted fields inside a replaced section use schema defaults where available.

## Without an explicit profile

When `config.file` is not declared, Skiller looks for `agent.json` next to the workflow YAML. If that file exists, it overrides the global configuration using the same rules. Otherwise, the agent uses only the global configuration.

See [Global agent configuration](/docs/configuration/global-agent/) for available fields and defaults.
