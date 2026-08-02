## Skiller user quick guide

Use this as a short user manual for Skiller. Keep answers concrete and point to repository docs for details.

### What Skiller is

Skiller runs YAML-defined workflows. A workflow is made of steps. A run is one execution of a workflow. An agent step lets an LLM work with configured tools.


### Essential commands
Use `--help` on each command for exact flags.

- `skiller run ...`: start a flow.
- `skiller status ...`: status run.
- `skiller logs ...`: show run logs/transcript.
- `skiller agent..`: show tools available to the run agent.
- `skiller --help` and `skiller <command> --help`: command-specific usage.

Command reference: `<path-docs>/cli/commands/`

### Configuration basics

Skiller resolves state from the current environment, working directory, and agent configuration.

- `AGENT_DB_PATH`: selects the runtime database.
- `cwd`: affects relative paths and `.env.development` loading.
- `.env.development`: can set defaults such as `AGENT_DB_PATH`.
- Global agent config: shared defaults stored in the user-level Skiller settings area.
- Local agent config: project or agent-specific config, usually near the selected agent/flow.

Local config should override global defaults when both define the same setting. If a run is not found, first verify the DB path, current working directory, and which agent config was loaded.

### Reading a flow YAML

Common fields:

- `steps`: ordered or named workflow steps.
- `agent`: declares an agent step.
- `system`: step-specific system instruction.
- `instructions`: reusable instruction blocks appended after `system`.
- `task`: user request or templated task for the agent.
- `tools`: tools enabled for the agent step.
- `next`: next step after completion.

Reference: `<path-docs>/flows/flow-schema.md`


### Quick troubleshooting

- `RUN_NOT_FOUND`: likely wrong `AGENT_DB_PATH` or `cwd`.
- Tools missing or blocked: check `skiller agent tools <run_id>`.
- Command blocked: inspect shell allowlist and allowed paths in agent tools.
- Unexpected prompt behavior: check `system`, `instructions`, and agent step docs.
- Runtime behavior unclear: inspect logs with `skiller logs <run_id>`.

### Documentation map

- Flow schema: `<path-docs>/flows/flow-schema.md`
- Agent step: `<path-docs>/steps/agent.md`
- Runtime architecture: `<path-docs>/architecture/architecture.md`
- Runtime development rules: `<path-docs>/architecture/dev-rules.md`
- Runtime code style: `<path-docs>/architecture/code-style.md`
