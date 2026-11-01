## Create Flows

### What A Flow Is

A flow is a declarative `.yaml` program. It defines named steps and their execution path; Skiller Runtime executes it.

### Start With The Flow Schema

Use `<path-docs>/flows/flow-schema.md` as the source of truth for root fields, steps, inputs, templates, and end actions.

### Flow Location And Naming

Keep related flows together, for example `flows/<group>/<name>.yaml`. Use stable, descriptive flow and step names.

### Define The Execution Path

Set `start` to an existing first step. Use `next` for normal progression and ensure every target exists. Use `when` or `switch` for conditional paths and provide a safe fallback for user-controlled input.

### Choose Step Types

Read `<path-docs>/steps/<step-type>.md` before using a step. Prefer the smallest existing step type: `assign` for values, `when` and `switch` for routing, waits for external input, `shell` for bounded local commands, `agent` for LLM work, `mcp` for external tools, and `notify` or `send` for output.

### Pass Inputs And Step Outputs

Declare values needed when the flow starts as `inputs`. Read prior outputs with `{{output_value("step_id").field}}`; do not read `step_executions.<step_id>.output.value` directly.

### Use Template Context

Use `<path-docs>/flows/flow-context.md` for template namespaces and output shapes. Common values are `{{flow.dir}}`, `{{flow.run_id}}`, and `{{runtime.python}}`.

### Select Agent Configuration Explicitly

For each new or updated `agent` step, prefer an explicit profile:

```yaml
- agent: reviewer
  config:
    file: "./profiles/reviewer.json"
  system: "Review the requested changes."
  task: "{{inputs.task}}"
```

`config` must contain exactly `file`, a non-empty string. References accept
absolute paths, `~`, relative paths, `$PROFILE_FILE`, and concatenations such as
`${PROFILE_DIR}/reviewer.json`. Variables come from the Runtime environment;
missing or empty variables are errors. Expansion happens once, without shell
execution. Relative results start at the directory containing the flow YAML.
Do not use templates such as `{{flow.dir}}`, `{{env.PROFILE_FILE}}`, or
`{{inputs.profile}}` in `config.file`. An explicit missing or invalid profile
fails without falling back to another file.

The selected profile overrides global configuration by root section, without
recursive merging, and replaces the conventional local profile. Implicit
`agent.json` discovery beside the YAML still works but is planned for
deprecation; do not rely on it for new flows. This does not deprecate the global
`~/.skiller/settings/agent.json`. Read `<path-docs>/agent/agent-config.md` and
`skiller-permissions` before configuring tools or changing model settings.

### Load A System Prompt From A File

`system` can remain inline or load a UTF-8 file with the same reference syntax as
`config.file`:

```yaml
system:
  file: "${PROMPT_DIR}/reviewer.md"
```

Absolute paths, `~`, and external files are supported; relative paths start at
the flow YAML directory. Missing/empty variables and file read errors fail
without fallback. Do not use `{{...}}` templates in `system.file`; file contents
are loaded as text without template expansion. `instructions` uses the same path rules for non-slug references, including
external files.

### Add Reusable Instructions

Keep `instructions` as an ordered list of strings. A slug matching
`[a-z][a-z0-9_-]*` loads `apps/instructions/<slug>.md`. Every other value is a file
reference using the same expansion as `config.file` and `system.file`:

```yaml
instructions:
  - "response-style"
  - "rules.md"
  - "../shared/security.md"
  - "${INSTRUCTIONS_DIR}/${PROFILE_NAME}.md"
```

Classification happens before variable expansion. Use `./response-style` for a
local file whose name is a slug. No fallback occurs between packaged and file
sources. Do not use `{{...}}` in references; loaded contents are plain UTF-8 text
appended after `system` in the declared order. Missing/empty variables and read
errors fail. Omit the field or use `[]` for no instructions, not null.

### Use Flow-Local Helpers

In template-enabled fields, reference files beside the YAML with `{{flow.dir}}`.
Run Python helpers with `{{runtime.python}}`, not `python` or `python3` from
`PATH`. For the agent shell tool, the helper paths and effective `cwd` must be
explicitly permitted, and the executable must be authorized when the command
allowlist is enabled. The automatic Runtime Python path permission does not
permit its command or the entire venv. A flow `shell` step and the agent's
`shell` tool are different contracts; read their respective documentation.

Relative tool permission paths start at the flow directory, not the selected
profile directory. Neither `{{flow.dir}}` nor `{{runtime.cwd}}` grants automatic
access. Tool-call paths have execution semantics: `files.path` starts at the
Runtime working directory; command paths start at shell's effective `cwd`.
Moving a profile must not change the base of its configured permission paths.

### Define User-Facing Messages And Actions

Keep prompts and messages concise and actionable. Use the schema and `<path-docs>/steps/notify.md` for flow end actions and notify actions.

### Handle Branches And Failures

Make each branch explicit. Ensure expected failure paths give the user a useful outcome and only add root end actions when the run needs one.

### Keep Flows Safe

Do not store secrets in YAML, prompts, examples, or output. Keep business logic out of large shell commands. Do not put TUI-only behavior in Runtime flows or run destructive/external actions without explicit approval.

### Validate Flow Structure

Use `<path-docs>/flows/flow-checker.md` to validate YAML structure, required fields, the step graph, and output references.

### Verify Runtime Readiness

Use `<path-docs>/flows/flow-readiness-checker.md` when a flow depends on local services such as webhooks or channels.

### Test A Flow Safely

Use an isolated `SKILLER_DB_PATH` for end-to-end checks. Do not test flows that change user configuration, credentials, external services, or user data without explicit approval.

Run a flow from an effective `flow_paths` entry with its canonical `@` reference, or pass its YAML path directly:

```bash
skiller run @group/name
skiller run ./flows/group/name.yaml
```

Use repeatable `--arg key=value` options for declared inputs. Add `--detach` only when the caller should return immediately after worker dispatch.

### Common Mistakes

Avoid missing `start` or `next` targets, invalid output paths, undeclared inputs, unsafe branch fallbacks, secrets in flow content, and oversized shell steps.
