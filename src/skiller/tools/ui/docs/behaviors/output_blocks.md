# Output Blocks

### Trigger
The UI appends a new command result to the output transcript.

### Structure
Each result is rendered as a readable block instead of a single dense line.
Run execution blocks follow [`run_transcript.md`](/home/fede/develop/py/skiller/src/skiller/tools/ui/docs/behaviors/run_transcript.md).

### Block Title
Most blocks start with a run header:

Examples:

`run-30bc: notify_test`
`run-dfd9: chat`
`run: story_route`

### Block Content
Content depends on the result kind.

Examples:

`  step_id [step_type]`
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
