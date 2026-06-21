# Flow File Checker

## Goal

`FlowCheckerUseCase` loads and validates a YAML flow definition before run creation.

Scope:
- raw file structure
- step graph integrity
- required fields by step type
- template rules for `output_value(...)`

It does not depend on runtime state.

## Global Rules

The checker returns `FLOW_*` error codes for YAML flow validation.

| Code | Condition | Message Template |
|---|---|---|
| `FLOW_FORMAT_INVALID` | the raw file payload is not an object | `FLOW_FORMAT_INVALID: flow must be an object` |
| `FLOW_NAME_MISSING` | root field `name` is missing or empty | `FLOW_NAME_MISSING: flow requires non-empty name` |
| `FLOW_START_MISSING` | root field `start` is missing or empty | `FLOW_START_MISSING: flow requires non-empty start` |
| `FLOW_STEPS_MISSING` | root field `steps` is missing | `FLOW_STEPS_MISSING: flow requires steps` |
| `FLOW_STEPS_INVALID` | `steps` exists but is not a list | `FLOW_STEPS_INVALID: flow steps must be a list` |
| `FLOW_STEPS_EMPTY` | `steps` exists but is empty | `FLOW_STEPS_EMPTY: flow requires at least one step` |
| `FLOW_START_STEP_NOT_FOUND` | `start` does not reference an existing `step_id` | `FLOW_START_STEP_NOT_FOUND: start references unknown step_id (start={start_step_id})` |
| `FLOW_END_ACTION_INVALID` | `on_success` or `on_error` exists but is not an object | `FLOW_END_ACTION_INVALID: end action config must be an object (trigger={trigger})` |
| `FLOW_END_ACTION_ACTION_INVALID` | `on_success` or `on_error` has neither an action object nor `cleanup: true` | `FLOW_END_ACTION_ACTION_INVALID: end action requires action object or cleanup true (trigger={trigger})` |
| `FLOW_END_ACTION_CLEANUP_INVALID` | root end action `cleanup` exists but is not boolean | `FLOW_END_ACTION_CLEANUP_INVALID: end action cleanup must be boolean (trigger={trigger})` |
| `FLOW_END_ACTION_TYPE_UNSUPPORTED` | root end action type is not `run` or `post` | `FLOW_END_ACTION_TYPE_UNSUPPORTED: end action type must be run or post (trigger={trigger})` |
| `FLOW_END_ACTION_LABEL_MISSING` | root end action has no non-empty `label` | `FLOW_END_ACTION_LABEL_MISSING: end action requires non-empty label (trigger={trigger})` |
| `FLOW_END_ACTION_ARG_MISSING` | root end action has no non-empty `arg` | `FLOW_END_ACTION_ARG_MISSING: end action requires non-empty arg (trigger={trigger})` |
| `FLOW_END_ACTION_PARAMS_INVALID` | root end action `params` exists but is not a string | `FLOW_END_ACTION_PARAMS_INVALID: end action params must be string (trigger={trigger})` |
| `FLOW_END_ACTION_AUTO_INVALID` | root end action `auto` exists but is not boolean | `FLOW_END_ACTION_AUTO_INVALID: end action auto must be boolean (trigger={trigger})` |
| `FLOW_STEP_PRIMARY_HEADER_MISSING` | a step item has no primary header like `notify`, `shell`, `switch`, etc. | `FLOW_STEP_PRIMARY_HEADER_MISSING: step requires a primary header (index={step_index})` |
| `FLOW_STEP_PRIMARY_HEADER_INVALID` | a step uses an unsupported primary header | `FLOW_STEP_PRIMARY_HEADER_INVALID: unsupported step type (index={step_index}, step_type={step_type})` |
| `FLOW_STEP_ID_MISSING` | a step primary header has an empty `step_id` | `FLOW_STEP_ID_MISSING: step requires non-empty step_id (index={step_index}, step_type={step_type})` |
| `FLOW_STEP_ID_DUPLICATED` | the same `step_id` appears more than once | `FLOW_STEP_ID_DUPLICATED: duplicated step_id (step_id={step_id})` |

## Step Rules

| Code | Condition | Message Template |
|---|---|---|
| `FLOW_STEP_NEXT_EMPTY` | `next` exists but is empty | `FLOW_STEP_NEXT_EMPTY: next requires non-empty target (step={step_id})` |
| `FLOW_STEP_NEXT_NOT_FOUND` | `next` references an unknown `step_id` | `FLOW_STEP_NEXT_NOT_FOUND: next references unknown step_id (step={step_id}, next={target_step_id})` |
| `FLOW_NOTIFY_MESSAGE_MISSING` | `notify` step has no `message` | `FLOW_NOTIFY_MESSAGE_MISSING: notify step requires message (step={step_id})` |
| `FLOW_NOTIFY_FORMAT_UNSUPPORTED` | `notify.format` is not `simple`, `structured`, or `markdown` | `FLOW_NOTIFY_FORMAT_UNSUPPORTED: notify step format must be simple, structured or markdown (step={step_id}, format={format})` |
| `FLOW_SEND_CHANNEL_MISSING` | `send` step has no `channel` | `FLOW_SEND_CHANNEL_MISSING: send step requires channel (step={step_id})` |
| `FLOW_SEND_KEY_MISSING` | `send` step has no `key` | `FLOW_SEND_KEY_MISSING: send step requires key (step={step_id})` |
| `FLOW_SEND_MESSAGE_MISSING` | `send` step has no `message` | `FLOW_SEND_MESSAGE_MISSING: send step requires message (step={step_id})` |
| `FLOW_SEND_CHANNEL_UNSUPPORTED` | `send` step uses an unsupported channel | `FLOW_SEND_CHANNEL_UNSUPPORTED: send step uses an unsupported channel (step={step_id}, channel={channel})` |
| `FLOW_SHELL_COMMAND_MISSING` | `shell` step has no `command` | `FLOW_SHELL_COMMAND_MISSING: shell step requires command (step={step_id})` |
| `FLOW_WAIT_INPUT_PROMPT_MISSING` | `wait_input` step has no `prompt` | `FLOW_WAIT_INPUT_PROMPT_MISSING: wait_input step requires prompt (step={step_id})` |
| `FLOW_WAIT_WEBHOOK_WEBHOOK_MISSING` | `wait_webhook` step has no `webhook` | `FLOW_WAIT_WEBHOOK_WEBHOOK_MISSING: wait_webhook step requires webhook (step={step_id})` |
| `FLOW_WAIT_WEBHOOK_KEY_MISSING` | `wait_webhook` step has no `key` | `FLOW_WAIT_WEBHOOK_KEY_MISSING: wait_webhook step requires key (step={step_id})` |
| `FLOW_WAIT_CHANNEL_CHANNEL_MISSING` | `wait_channel` step has no `channel` | `FLOW_WAIT_CHANNEL_CHANNEL_MISSING: wait_channel step requires channel (step={step_id})` |
| `FLOW_WAIT_CHANNEL_KEY_MISSING` | `wait_channel` step has no `key` | `FLOW_WAIT_CHANNEL_KEY_MISSING: wait_channel step requires key (step={step_id})` |
| `FLOW_MCP_SERVER_MISSING` | `mcp` step has no `server` | `FLOW_MCP_SERVER_MISSING: mcp step requires server (step={step_id})` |
| `FLOW_MCP_TOOL_MISSING` | `mcp` step has no `tool` | `FLOW_MCP_TOOL_MISSING: mcp step requires tool (step={step_id})` |
| `FLOW_SWITCH_CASE_TARGET_NOT_FOUND` | a `switch` case points to an unknown step | `FLOW_SWITCH_CASE_TARGET_NOT_FOUND: switch case references unknown step_id (step={step_id}, target={target_step_id})` |
| `FLOW_SWITCH_DEFAULT_TARGET_NOT_FOUND` | `switch.default` points to an unknown step | `FLOW_SWITCH_DEFAULT_TARGET_NOT_FOUND: switch default references unknown step_id (step={step_id}, target={target_step_id})` |
| `FLOW_WHEN_BRANCH_TARGET_NOT_FOUND` | a `when` branch points to an unknown step | `FLOW_WHEN_BRANCH_TARGET_NOT_FOUND: when branch references unknown step_id (step={step_id}, target={target_step_id})` |
| `FLOW_WHEN_DEFAULT_TARGET_NOT_FOUND` | `when.default` points to an unknown step | `FLOW_WHEN_DEFAULT_TARGET_NOT_FOUND: when default references unknown step_id (step={step_id}, target={target_step_id})` |

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
body(...)
output(...)
outputValue(...)
output_value()
output_value("a", "b")
output_value(dynamic_var)
```

| Code | Condition | Message Template |
|---|---|---|
| `FLOW_OUTPUT_VALUE_INVALID_SYNTAX` | invalid `output_value(...)` expression shape | `FLOW_OUTPUT_VALUE_INVALID_SYNTAX: invalid output_value expression (step={step_id}, field={field})` |
| `FLOW_OUTPUT_VALUE_INVALID_ARITY` | `output_value(...)` does not receive exactly one argument | `FLOW_OUTPUT_VALUE_INVALID_ARITY: output_value expects exactly one argument (step={step_id}, field={field})` |
| `FLOW_OUTPUT_VALUE_STEP_ID_NOT_LITERAL` | the argument is not a string literal | `FLOW_OUTPUT_VALUE_STEP_ID_NOT_LITERAL: output_value step_id must be a string literal (step={step_id}, field={field})` |
| `FLOW_OUTPUT_VALUE_STEP_NOT_FOUND` | referenced `step_id` does not exist in the file | `FLOW_OUTPUT_VALUE_STEP_NOT_FOUND: referenced step_id does not exist (step={step_id}, ref={ref_step_id})` |
| `FLOW_OUTPUT_VALUE_FORWARD_REFERENCE` | referenced `step_id` is the current step or is declared after the current step | `FLOW_OUTPUT_VALUE_FORWARD_REFERENCE: output_value must reference a previous step (step={step_id}, ref={ref_step_id})` |
| `FLOW_OUTPUT_VALUE_DIRECT_OUTPUT_ACCESS` | template accesses `output.value` directly through `step_executions` | `FLOW_OUTPUT_VALUE_DIRECT_OUTPUT_ACCESS: direct output.value access is not allowed (step={step_id}, field={field})` |
| `FLOW_OUTPUT_VALUE_UNSUPPORTED_HELPER` | template uses an unsupported helper | `FLOW_OUTPUT_VALUE_UNSUPPORTED_HELPER: unsupported template helper (step={step_id}, field={field})` |

## Runtime Boundary

`FlowCheckerUseCase` does not verify runtime-only conditions such as:
- whether a referenced step has already executed in a specific run
- whether the resolved output body contains a requested field path

Those checks belong to execution-time rendering.

Server availability before run creation is handled separately by
[`flow-readiness-checker.md`](flow-readiness-checker.md).
