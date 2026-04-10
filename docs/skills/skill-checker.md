# Skill Checker

## Goal

`SkillCheckerUseCase` loads and validates a skill before run creation.

Scope:
- raw skill structure
- step graph integrity
- required fields by step type
- template rules for `output_value(...)`

It does not depend on runtime state.

## Global Rules

| Code | Condition | Message Template |
|---|---|---|
| `SKILL_FORMAT_INVALID` | the raw skill payload is not an object | `SKILL_FORMAT_INVALID: skill must be an object` |
| `SKILL_NAME_MISSING` | root field `name` is missing or empty | `SKILL_NAME_MISSING: skill requires non-empty name` |
| `SKILL_START_MISSING` | root field `start` is missing or empty | `SKILL_START_MISSING: skill requires non-empty start` |
| `SKILL_STEPS_MISSING` | root field `steps` is missing | `SKILL_STEPS_MISSING: skill requires steps` |
| `SKILL_STEPS_INVALID` | `steps` exists but is not a list | `SKILL_STEPS_INVALID: skill steps must be a list` |
| `SKILL_STEPS_EMPTY` | `steps` exists but is empty | `SKILL_STEPS_EMPTY: skill requires at least one step` |
| `SKILL_START_STEP_NOT_FOUND` | `start` does not reference an existing `step_id` | `SKILL_START_STEP_NOT_FOUND: start references unknown step_id (start={start_step_id})` |
| `SKILL_STEP_PRIMARY_HEADER_MISSING` | a step item has no primary header like `notify`, `shell`, `switch`, etc. | `SKILL_STEP_PRIMARY_HEADER_MISSING: step requires a primary header (index={step_index})` |
| `SKILL_STEP_PRIMARY_HEADER_INVALID` | a step uses an unsupported primary header | `SKILL_STEP_PRIMARY_HEADER_INVALID: unsupported step type (index={step_index}, step_type={step_type})` |
| `SKILL_STEP_ID_MISSING` | a step primary header has an empty `step_id` | `SKILL_STEP_ID_MISSING: step requires non-empty step_id (index={step_index}, step_type={step_type})` |
| `SKILL_STEP_ID_DUPLICATED` | the same `step_id` appears more than once | `SKILL_STEP_ID_DUPLICATED: duplicated step_id (step_id={step_id})` |

## Step Rules

| Code | Condition | Message Template |
|---|---|---|
| `SKILL_STEP_NEXT_EMPTY` | `next` exists but is empty | `SKILL_STEP_NEXT_EMPTY: next requires non-empty target (step={step_id})` |
| `SKILL_STEP_NEXT_NOT_FOUND` | `next` references an unknown `step_id` | `SKILL_STEP_NEXT_NOT_FOUND: next references unknown step_id (step={step_id}, next={target_step_id})` |
| `SKILL_NOTIFY_MESSAGE_MISSING` | `notify` step has no `message` | `SKILL_NOTIFY_MESSAGE_MISSING: notify step requires message (step={step_id})` |
| `SKILL_SEND_CHANNEL_MISSING` | `send` step has no `channel` | `SKILL_SEND_CHANNEL_MISSING: send step requires channel (step={step_id})` |
| `SKILL_SEND_KEY_MISSING` | `send` step has no `key` | `SKILL_SEND_KEY_MISSING: send step requires key (step={step_id})` |
| `SKILL_SEND_MESSAGE_MISSING` | `send` step has no `message` | `SKILL_SEND_MESSAGE_MISSING: send step requires message (step={step_id})` |
| `SKILL_SEND_CHANNEL_UNSUPPORTED` | `send` step uses an unsupported channel | `SKILL_SEND_CHANNEL_UNSUPPORTED: send step supports only whatsapp (step={step_id}, channel={channel})` |
| `SKILL_SHELL_COMMAND_MISSING` | `shell` step has no `command` | `SKILL_SHELL_COMMAND_MISSING: shell step requires command (step={step_id})` |
| `SKILL_WAIT_INPUT_PROMPT_MISSING` | `wait_input` step has no `prompt` | `SKILL_WAIT_INPUT_PROMPT_MISSING: wait_input step requires prompt (step={step_id})` |
| `SKILL_WAIT_WEBHOOK_WEBHOOK_MISSING` | `wait_webhook` step has no `webhook` | `SKILL_WAIT_WEBHOOK_WEBHOOK_MISSING: wait_webhook step requires webhook (step={step_id})` |
| `SKILL_WAIT_WEBHOOK_KEY_MISSING` | `wait_webhook` step has no `key` | `SKILL_WAIT_WEBHOOK_KEY_MISSING: wait_webhook step requires key (step={step_id})` |
| `SKILL_WAIT_CHANNEL_CHANNEL_MISSING` | `wait_channel` step has no `channel` | `SKILL_WAIT_CHANNEL_CHANNEL_MISSING: wait_channel step requires channel (step={step_id})` |
| `SKILL_WAIT_CHANNEL_KEY_MISSING` | `wait_channel` step has no `key` | `SKILL_WAIT_CHANNEL_KEY_MISSING: wait_channel step requires key (step={step_id})` |
| `SKILL_MCP_SERVER_MISSING` | `mcp` step has no `server` | `SKILL_MCP_SERVER_MISSING: mcp step requires server (step={step_id})` |
| `SKILL_MCP_TOOL_MISSING` | `mcp` step has no `tool` | `SKILL_MCP_TOOL_MISSING: mcp step requires tool (step={step_id})` |
| `SKILL_SWITCH_CASE_TARGET_NOT_FOUND` | a `switch` case points to an unknown step | `SKILL_SWITCH_CASE_TARGET_NOT_FOUND: switch case references unknown step_id (step={step_id}, target={target_step_id})` |
| `SKILL_SWITCH_DEFAULT_TARGET_NOT_FOUND` | `switch.default` points to an unknown step | `SKILL_SWITCH_DEFAULT_TARGET_NOT_FOUND: switch default references unknown step_id (step={step_id}, target={target_step_id})` |
| `SKILL_WHEN_BRANCH_TARGET_NOT_FOUND` | a `when` branch points to an unknown step | `SKILL_WHEN_BRANCH_TARGET_NOT_FOUND: when branch references unknown step_id (step={step_id}, target={target_step_id})` |
| `SKILL_WHEN_DEFAULT_TARGET_NOT_FOUND` | `when.default` points to an unknown step | `SKILL_WHEN_DEFAULT_TARGET_NOT_FOUND: when default references unknown step_id (step={step_id}, target={target_step_id})` |

## Template Rules

Allowed helper:

```text
output_value("step_id")
output_value("step_id").field
output_value("step_id").nested.field
```

Rules:
- helper name must be `output_value`
- exactly one argument
- the argument must be a string literal
- the string literal is the referenced `step_id`
- optional field access may follow after the helper call

Forbidden patterns:

```text
step_executions.<step_id>.output.value
step_executions.<step_id>.output.body_ref
body(...)
output(...)
outputValue(...)
output_value()
output_value("a", "b")
output_value(dynamic_var)
```

| Code | Condition | Message Template |
|---|---|---|
| `SKILL_OUTPUT_VALUE_INVALID_SYNTAX` | invalid `output_value(...)` expression shape | `SKILL_OUTPUT_VALUE_INVALID_SYNTAX: invalid output_value expression (step={step_id}, field={field})` |
| `SKILL_OUTPUT_VALUE_INVALID_ARITY` | `output_value(...)` does not receive exactly one argument | `SKILL_OUTPUT_VALUE_INVALID_ARITY: output_value expects exactly one argument (step={step_id}, field={field})` |
| `SKILL_OUTPUT_VALUE_STEP_ID_NOT_LITERAL` | the argument is not a string literal | `SKILL_OUTPUT_VALUE_STEP_ID_NOT_LITERAL: output_value step_id must be a string literal (step={step_id}, field={field})` |
| `SKILL_OUTPUT_VALUE_STEP_NOT_FOUND` | referenced `step_id` does not exist in the skill | `SKILL_OUTPUT_VALUE_STEP_NOT_FOUND: referenced step_id does not exist (step={step_id}, ref={ref_step_id})` |
| `SKILL_OUTPUT_VALUE_FORWARD_REFERENCE` | referenced `step_id` is the current step or is declared after the current step | `SKILL_OUTPUT_VALUE_FORWARD_REFERENCE: output_value must reference a previous step (step={step_id}, ref={ref_step_id})` |
| `SKILL_OUTPUT_VALUE_DIRECT_OUTPUT_ACCESS` | template accesses `output.value` directly through `step_executions` | `SKILL_OUTPUT_VALUE_DIRECT_OUTPUT_ACCESS: direct output.value access is not allowed (step={step_id}, field={field})` |
| `SKILL_OUTPUT_VALUE_BODY_REF_DIRECT_ACCESS` | template accesses `output.body_ref` directly | `SKILL_OUTPUT_VALUE_BODY_REF_DIRECT_ACCESS: direct body_ref access is not allowed (step={step_id}, field={field})` |
| `SKILL_OUTPUT_VALUE_UNSUPPORTED_HELPER` | template uses an unsupported helper | `SKILL_OUTPUT_VALUE_UNSUPPORTED_HELPER: unsupported template helper (step={step_id}, field={field})` |

## Runtime Boundary

`SkillCheckerUseCase` does not verify runtime-only conditions such as:
- whether a referenced step has already executed in a specific run
- whether a persisted `body_ref` can be resolved from DB
- whether the resolved output body contains a requested field path

Those checks belong to execution-time rendering.

Server availability before run creation is handled separately by
[`skills/skill-server-checker.md`](skill-server-checker.md).
