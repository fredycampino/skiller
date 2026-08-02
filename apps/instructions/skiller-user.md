## Skiller user quick guide

Use this as a short user manual for Skiller. Keep answers concrete and point to repository docs for details.

### What Skiller is

Skiller runs YAML-defined workflows. A workflow is made of steps. A run is one execution of a workflow. An agent step lets an LLM work with configured tools.

Reference: `packages/skiller/docs/architecture/architecture.md`

### Basic workflow

1. Choose or create a flow YAML.
2. Run the flow with `skiller run ...`.
3. List executions with `skiller runs`.
4. Inspect a run with `skiller logs <run_id>`.
5. Inspect agent tools with `skiller agent tools <run_id>`.

Use `--help` on each command for exact flags.

References:
- `packages/skiller/docs/flows/flow-schema.md`
- `packages/skiller/docs/steps/agent.md`

### Essential commands

- `skiller run ...`: start a flow.
- `skiller runs`: list known runs in the configured DB.
- `skiller logs <run_id>`: show run logs/transcript.
- `skiller agent tools <run_id>`: show tools available to the run agent.
- `skiller --help` and `skiller <command> --help`: command-specific usage.

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

Reference: `packages/skiller/docs/flows/flow-schema.md`

### Reusable instructions

Use `instructions` for reusable system prompt fragments.

Examples:
- `"skiller-user"`: packaged instruction from `apps/instructions/skiller-user.md`.
- `"solve-task-style"`: packaged instruction from `apps/instructions/solve-task-style.md`.
- `"./repo-rules.md"`: local file relative to the flow YAML.

Reference: `packages/skiller/docs/steps/agent.md`

### Quick troubleshooting

- `RUN_NOT_FOUND`: likely wrong `AGENT_DB_PATH` or `cwd`.
- Tools missing or blocked: check `skiller agent tools <run_id>`.
- Command blocked: inspect shell allowlist and allowed paths in agent tools.
- Unexpected prompt behavior: check `system`, `instructions`, and agent step docs.
- Runtime behavior unclear: inspect logs with `skiller logs <run_id>`.

### Documentation map

- Flow schema: `packages/skiller/docs/flows/flow-schema.md`
- Agent step: `packages/skiller/docs/steps/agent.md`
- Runtime architecture: `packages/skiller/docs/architecture/architecture.md`
- Runtime development rules: `packages/skiller/docs/architecture/dev-rules.md`
- Runtime code style: `packages/skiller/docs/architecture/code-style.md`
