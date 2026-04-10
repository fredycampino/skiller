# Run Transcript

### Goal
Define how `/run` and follow-up execution updates are rendered in the `Output` transcript.

### Scope
This behavior applies to:
- `/run`
- automatic follow-up `watch` after `/run`
- automatic follow-up `watch` after `wait_input` replies
- explicit `/watch`

It does not define `/logs`, which stays raw and debug-oriented under [`logs-debug.md`](logs-debug.md).

### Header
Each execution block starts with a single run header:

Examples:

`[run-create] chat:7f1f`
`[run-resume] chat:7f1f`
`[run-create] notify_test:30bc`

Rules:
- `/run` starts with `[run-create]`
- follow-up execution after resume/input starts with `[run-resume]`
- the suffix is the last 4 characters of the `run_id`

### Step Lines
Each visible step is rendered as:

`  [step_type] [step_id]`

If the step has user-facing output, it is rendered on the next line:

`    [result]`

Examples:

`  [switch] decide_exit`
`    answer`

`  [llm_prompt] answer`
`    España tiene 50 provincias.`

`  [wait_input] ask_user`
`    Write a message. Type exit, quit, or bye to stop.`

### Event Mapping
The transcript is built from generic runtime events only.
It must not depend on raw watch text or `stderr` parsing.

Visible mappings:
- `STEP_SUCCESS` -> visible step line
- `RUN_WAITING` -> visible waiting step line
- `STEP_ERROR` -> error block
- `RUN_FINISHED` with failed status -> error block

Ignored in the user transcript:
- `RUN_CREATE`
- `RUN_RESUME`
- `STEP_STARTED`
- `RUN_FINISHED` with waiting status
- `RUN_FINISHED` with succeeded status when the executed steps already explain the turn

### Waiting Steps
`RUN_WAITING` renders the active waiting step.

Examples:
- `wait_input` -> prompt
- `wait_webhook` -> webhook or webhook:key
- `wait_channel` -> channel or channel:key

### Hidden Resolved Wait Steps
Resolved `wait_input` and `wait_webhook` `STEP_SUCCESS` events are not shown in the user transcript.

Reason:
- they are technical resume events
- they duplicate the previous wait and make the flow harder to scan

`wait_channel` is different:
- resolved `wait_channel` `STEP_SUCCESS` events stay visible
- they carry the channel/key that actually resumed the run
- they help explain why the next steps executed

### Incremental Behavior
The transcript must append only new events for the run.

Rules:
- each run keeps a set of seen `event_id`s in the UI session
- a `watch` block renders only unseen events
- the block must not re-render the whole run history

### Leading Waiting Trim
When a new execution block contains real execution after an older waiting marker, the stale leading `RUN_WAITING` must be omitted.

Example:
- old block ended in `[wait_input] ask_user`
- next block begins with resume metadata and the same old waiting event
- the transcript must start at the first new visible step, not at the stale waiting line

### Errors
Errors render as:

`  ↳ error`
`    [message]`

Tracebacks and provider errors must be reduced to a concise readable message.

### Example

```text
[run-resume] chat:7f1f
  [wait_channel] listen_whatsapp
    Channel message received: whatsapp:172584771580071@lid.
  [notify] notify_message
    WhatsApp recibido: hola
```
