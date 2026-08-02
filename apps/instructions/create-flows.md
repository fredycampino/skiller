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

### Use Flow-Local Helpers

Reference files beside the YAML with `{{flow.dir}}`. Run Python helpers with `{{runtime.python}}`, not `python` or `python3` from `PATH`.

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

Use an isolated `AGENT_DB_PATH` for end-to-end checks. Do not test flows that change user configuration, credentials, external services, or user data without explicit approval.

### Common Mistakes

Avoid missing `start` or `next` targets, invalid output paths, undeclared inputs, unsafe branch fallbacks, secrets in flow content, and oversized shell steps.
