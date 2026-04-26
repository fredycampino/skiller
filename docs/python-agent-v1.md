# Python Agent V1 Spike

## Goal

Define a minimal Python agent built specifically for Skiller.

The agent should be able to:

- create `skills/*.yaml`
- edit existing skills
- validate skill contracts
- run skills through the current runtime
- inspect run status and logs

V1 should reuse the current Skiller runtime and CLI instead of inventing a second execution model.

## Positioning

This is not a customization of `pi`.

This is a Skiller-native agent in Python:

- same language as the runtime
- same repo
- same step contracts
- same operational commands

The value is direct integration with:

- skill YAML
- `SkillCheckerUseCase`
- `SkillServerCheckerUseCase`
- runtime status/logs/output

## V1 Scope

### In

- interactive CLI agent
- project-specific system prompt
- Python tools for reading and writing skill files
- validation through existing Skiller runtime and CLI
- execution through existing runtime commands
- repo-grounded answers about current step contracts

### Out

- multi-agent orchestration
- autonomous background planning
- long-term memory
- separate agent persistence model
- custom TUI
- replacing the current `skiller` runtime

## Design Rules

1. The agent does not execute skills itself.
2. The agent delegates execution to the current `skiller` runtime.
3. The agent does not define a second skill schema.
4. The agent should operate on normal project files and normal runtime commands.
5. V1 should be useful even if the only outputs are YAML files and CLI actions.

## Proposed V1 Architecture

### Components

1. `agent/cli.py`
   - entrypoint for interactive and one-shot mode

2. `agent/session.py`
   - in-memory conversation loop
   - short bounded history

3. `agent/prompts/system.md`
   - Skiller-specific system prompt
   - rules for YAML generation and repo conventions

4. `agent/tools/`
   - Python tools exposed to the LLM

5. `agent/runner.py`
   - tool loop
   - model invocation
   - final response assembly

## Proposed Tool Set

### File Tools

- `read_file(path)`
- `write_file(path, content)`
- `list_skills()`
- `read_skill(name)`

### Skiller Tools

- `validate_skill(name_or_path)`
- `run_skill(name_or_path, args)`
- `get_run_status(run_id)`
- `get_run_logs(run_id)`
- `get_execution_output(body_ref)`

### Repo Tools

- `search_repo(pattern)`
- `read_doc(path)`

## Integration Strategy

V1 should not import internal application services directly.

Instead, it should start by calling the existing CLI:

- `skiller run ...`
- `skiller status ...`
- `skiller logs ...`
- `skiller execution-output ...`

Reason:

- matches current operator workflow
- lower coupling
- easier to test
- avoids agent-only code paths

If the agent proves useful, later it can move from CLI wrappers to direct Python adapters.

## Proposed User Flows

### Create Skill

1. user describes desired behavior
2. agent reads relevant docs:
   - `docs/skills/skill-schema.md`
   - `docs/steps/*`
3. agent writes `skills/<name>.yaml`
4. agent validates the file
5. agent reports the final YAML and next command to run

### Fix Skill

1. user points to a failing skill
2. agent reads the YAML
3. agent reads checker or step docs
4. agent edits the file
5. agent validates again

### Operate Skill

1. user asks to run a skill
2. agent runs `skiller run ...`
3. agent reads status and logs
4. agent summarizes the outcome

## Minimal Prompt Contract

The system prompt should tell the agent:

- Skiller skills are YAML files under `skills/`
- use only supported step types documented in `docs/steps/`
- prefer explicit `next` transitions
- do not invent fields outside the documented schema
- validate before claiming a skill is ready
- when a step depends on external ingress, explain runtime prerequisites

## Why Python Makes Sense Here

- the runtime is already Python
- the CLI is already Python
- the domain model already exists here
- skill creation and runtime operation do not need a TypeScript bridge

## Expected Benefits

- faster authoring of real skills
- fewer invalid YAML attempts
- direct operational assistant for runs and waiting states
- no dependency on a second agent platform for core Skiller workflows

## Expected Pain Points

- the first version will need careful tool boundaries
- YAML generation may still need templates for consistency
- raw CLI output may need normalization before sending back to the model
- without a dedicated TUI, interactive UX will stay basic

## Recommendation

Build Python Agent V1 as a thin agent layer on top of the current `skiller` CLI and docs.

Do not create a second runtime.

Use it first for:

- skill authoring
- skill fixing
- run inspection

If that proves useful, later add:

- direct Python adapters instead of CLI wrappers
- a dedicated TUI
- richer templates for channel and webhook skills
