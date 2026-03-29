# UI Output

### Trigger
The UI appends a new command result to the output transcript.

### Structure
Each result is rendered as a readable block instead of a single dense line.
Run execution blocks follow [`transcript.md`](transcript.md).
`/logs` follows [`logs-debug.md`](logs-debug.md).

### Block Title
Run transcript blocks start with an execution header:

Examples:

`[run-create] notify_test:30bc`
`[run-resume] chat:d0e9`

Other result kinds may still use simple run headers such as:

`run-30bc: notify_test`
`run: story_route`

### Block Content
Content depends on the result kind.

Examples:

`  [step_type] [step_id]`
`    [result]`

`  ↳ error`
`    [message]`

### Separation
Blocks are appended in order.
Run transcript blocks do not rely on blank-line separation between internal steps.

### Error Result
An error block shows a concise error message.
Tracebacks must be reduced to a readable final message.

### Input Result
An input block shows whether the reply was accepted or rejected.

### Goal
The output transcript must remain easy to scan when multiple results are appended over time.
