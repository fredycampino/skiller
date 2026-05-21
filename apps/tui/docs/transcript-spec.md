# TUI Transcript Visual Spec

## Goal

Define how the TUI transcript should look.

This document is the visual source of truth for transcript output.

It does not define polling internals or rendering implementation details.

## Rendering Contract

The renderer is expected to map one transcript item to one visual renderable.

Reference only:

```python
render_transcript_item(item: TranscriptItem) -> RenderableType
```

This document defines how that result should look, not how it is implemented.

Transcript item modeling direction for this spec:
- `USER_INPUT`
- `DISPATCH_ERROR`
- `RUN_ACK`
- `RUN_RESUME`
- `RUN_STEP`
- `RUN_OUTPUT`
- `AGENT_ASSISTANT_MESSAGE`
- `AGENT_INTERRUPTED`
- `AGENT_MAX_TURNS_EXHAUSTED`
- `RUN_STATUS`
- `AGENT_TOOL_CALL`
- `AGENT_TOOL_RESULT`
- `INFO`

Notes:
- `DISPATCH_ERROR` is outside the run session block because no run was created
- `RUN_RESUME` opens a follow-up run session block after input is accepted
- `RUN_STATUS` belongs to the run session block
- `RUN_STATUS` covers states such as `waiting`, `succeeded`, and `error`

## Principles

- The transcript is a console transcript, not a chat transcript.
- It must feel operational and compact.
- It must not expose raw runtime event names to the user.
- It must not expose transport details from polling or CLI integration.
- It must prefer readable output over debug output.

## General Layout

- The user command appears with the user prompt icon.
- The run reply appears as a separate visual block.
- Each run reply is a run session block.
- There is one blank line between the user command and the run block.
- Inside a run block, blank lines are used sparingly to separate distinct execution phases.
- The transcript must be easy to scan top to bottom.

Example:

```text
› /run notify_test

↳ run(skill_name)
   created
[step_type] step_id
   {"message":"step result"}
  succeeded
```

## What Must Be Visible

The transcript should show:
- the user command
- the immediate run acknowledgment
- the visible execution steps
- user-facing step output
- the final status
- concise error messages

The transcript should not show:
- `USER` / `ASSISTANT` labels
- raw event names like `RUN_CREATE` or `STEP_STARTED`
- duplicated technical events
- tracebacks in normal flow

## Visual Blocks

### User Command

Show the command with the user prompt icon.

Example:

```text
› /run delay_test
```

## Run Acknowledgment

This opens the run session block.

Target shape:

```text
↳ run(delay_test)
   created 018f78a1-8148-4948-9566-39f69a13692f
```

Rules:
- keep `run(...)` on one line
- place the full `run_id` on the `created` line
- the acknowledgment must look like a console response to the command above

### Run Resume

When a waiting run accepts user input, the transcript should show a follow-up resume block.

Target shape:

```text
↳ resume(wait_input_test)
```

Rules:
- keep `resume(...)` on one line
- use the skill name that was previously associated with the run when available
- do not repeat the `created` line for the resumed run

### Dispatch Error

If the run cannot be created, the transcript should show an explicit error block instead of a run block.

Target shape:

```text
error:
  skill not found: notify_demo
```

Rules:
- do not render `run(...)` if creation failed
- do not show raw traceback in the normal transcript
- the error should explain the failure in user terms

Dispatch error is not a run session block because the run was never created.

## Run Step

A visible execution step should render as a compact line.

Target shape:

```text
[step_type] step_id
```

Rules:
- avoid raw runtime wording
- keep the line compact
- prefer step meaning over event naming
- include `step_type`
- include `step_id`
- align non-wait step headers with the `agent` header baseline

### Wait Steps (`wait_input` / `wait_webhook` / `wait_channel`)

Wait steps should render as a compact muted placeholder:

```text
   ...
```

Rules:
- do not render `[wait_input] ask_user` in transcript
- do not render run-local `waiting` line in transcript
- waiting prompt is shown in global status view: `Waiting [prompt]`

### Agent Step Accent

`[agent]` should use accent color to make agent execution easy to scan.

### Agent Step Structure

An `agent` step is one visual block.

That block may contain, in this order:
- one agent step header
- assistant text that introduces tool calls
- zero or more tool call / tool result pairs
- one final assistant message

Target direction:

```text
[agent] support_agent
‹ I will inspect the repository state.
  ▪ $ git status --short
      M src/...

‹ Done. The issue was in the mapper.
```

Rules:
- keep a single `[agent] step_id` header for the full agent step
- do not open a new agent step header for each internal assistant turn
- assistant natural-language text and tool lines belong to the same agent step block
- assistant natural-language text never uses the `▪` tool marker

### Agent Tool Lines

When an agent uses a tool, render the tool call as a muted operational line inside the agent step block.

Target shape in context:

```text
[agent] support_agent
  ▪ $ git status --short     # tool call
      src/skiller/...
```

Rules:
- the `▪` marker is muted
- the marker is only for agent tool calls
- tool output lines stay visually attached below the tool call
- the latest tool call stays visually active while it is the last item, or while only its tool output follows it

### Agent Tool Output

Tool results should render as an indented muted line under the tool call that produced them.

Target shape in context:

```text
[agent] support_agent
  ▪ $ git status --short
      src/skiller/...        # tool output
```
Rules:
- keep the tool output visually attached to the call above it
- use muted styling for the result line
- prefer a concise preview over the full raw tool payload when possible

### Agent Assistant Message

Assistant text inside an agent step may appear:
- before tool calls in the same internal turn
- after earlier tool calls in a later internal turn
- as the final message that closes the agent step

Target shape in context for prose:

```text
[agent] support_agent
‹ I will inspect the repository state.  # assistant message
  ▪ $ git status --short
```

Rules:
- prose assistant text uses the `‹` prefix
- assistant text that introduces tool calls must render before the first tool call of that turn
- assistant text remains part of the current agent step block
- assistant text is visually distinct from tool lines

### Agent final message

The final assistant message is the last natural-language message in the agent step block.

Target shape in context for simple text:

```text
[agent] support_agent
  ▪ $ git status
      M src/...

‹ message                              # final assistant message
```

Target shape in context for markdown that starts with prose:

```text
[agent] support_agent
  ▪ $ git status
      M src/...

‹ Changes:

  • item 1
  • item 2
```

Focused shape:

```text
‹ Changes:

  • item 1
  • item 2
```

Target shape in context for markdown that starts with fenced code:

~~~~text
[agent] support_agent
  ▪ $ git diff --stat
      3 files changed, 20 insertions(+), 4 deletions(-)

```diff
@@ -1 +1 @@
-old
+new
```

Changes:
1. item 1
2. item 2
~~~~

Focused block:

~~~~text
```diff
@@ -1 +1 @@
-old
+new
```

Changes:
1. item 1
2. item 2
~~~~

Rules:
- simple agent text uses the `‹` prefix
- markdown output keeps markdown formatting
- if markdown starts with prose, prefix the first visible line with `‹`
- if markdown starts with fenced code, do not force `‹` before the fence
- insert one blank line between the last tool result and the final agent message
- this separation applies when an `AgentToolResultItem` is immediately followed by a visible final `RunOutputItem(step_type="agent")`

### Agent system notifications

Some agent outcomes are not conversational agent replies.

They are system-level notifications emitted by the harness/runtime and must not be rendered with the agent reply prefix `‹`.

This applies to:
- `AGENT_INTERRUPTED`
- `AGENT_MAX_TURNS_EXHAUSTED`

Target shape in context for interrupt:

```text
[agent] support_agent
  ▪ $ pytest -q
      ...

  ! Interrupted by user
```

Target shape in context for max turns exhausted:

```text
[agent] support_agent
  ▪ $ rg "render_transcript" -n src
      src/...

  ! Turn limit reached
```

Rules:
- render these items as system notifications, not as agent chat messages
- use the `!` icon
- use warning color for both the icon and the text
- do not use the `‹` prefix
- do not style them as errors
- do not expect a final `AGENT_ASSISTANT_MESSAGE(message_type="final")` after them
- insert one blank line before the notification when it follows a tool block
- insert one blank line after the notification because it closes the current agent block

Runtime contract:
- normal final answer:
  - `AGENT_ASSISTANT_MESSAGE(message_type="final")`
  - `data.stop_reason = "final"`
  - `data.final.text` exists
- interrupt:
  - `AGENT_INTERRUPTED`
  - `data.stop_reason = "interrupted"`
  - `data.final = null`
  - no final assistant message
- max turns exhausted:
  - `AGENT_MAX_TURNS_EXHAUSTED`
  - `data.stop_reason = "max_turns_exhausted"`
  - `data.final = null`
  - no final assistant message

### Agent Multi-Turn Block

One `agent` step may contain more than one internal assistant turn.

Each internal turn may contribute:
- one assistant message that introduces tool calls
- zero or more tool call / tool result pairs

The last internal turn may end with the final assistant message.

Target shape:

```text
[agent] support_agent
‹ I will inspect the repository state.
  ▪ $ git status --short
      M src/...
  ▪ $ git diff --stat
      3 files changed, 20 insertions(+), 4 deletions(-)

‹ I still need to confirm the TUI change.
  ▪ $ rg "AGENT_TOOL_CALL" -n src
      src/...

‹ Done. The issue was in the mapper.
```

Rules:
- keep a single `[agent] step_id` header for the full agent step
- do not open a new agent step header for each internal turn
- each internal turn may contribute one assistant message and zero or more tool call / tool result pairs
- the final internal turn may end with a final assistant message
- blank lines may separate distinct internal turns inside the same agent step block



### Conditional Steps (`switch` / `when`)

Conditional routing should render inline in a single compact line.

Target shape:

```text
[switch] decide_exit → support_agent
```

Rules:
- this applies to `switch` and `when`
- the entire line uses muted style
- the selected target appears after `→`
- do not render an extra output line for this routing message

## Run Output

Run output is the visible result produced by the step above it.

It always belongs to the previous step line.

Example:

```text
[step_type] step_id
    visible result
```

Rules:
- output appears directly under the step that produced it
- output is optional; some steps may have no visible output
- output should show user-facing content, not transport/debug details
- if the step produced both a readable text and a larger structured payload, the readable content is preferred unless the structured payload is the intended visible result

### Simple Output

Simple output should render on one line:

```text
    visible result
```

Use this when the visible result is essentially a short message.

### Structured Output

Structured output may render as a formatted block under the step:

```text
[step_type] step_id
    {
      "body_ref": null,
      "text": "visible result",
      "value": {
        "message": "visible result"
      }
    }
```

Rules:
- structured output must be readable
- indentation must make nested content easy to scan
- the block must still read as the output of the step immediately above
- later the UI may summarize or collapse structured output, but this spec assumes visible content

### Markdown Output

Markdown output should render as markdown content (headings, lists, emphasis).

Target direction:

```text
[agent] support_agent
‹ item 1
  - item 2
```

Rules:
- use markdown rendering for rich assistant text
- keep the output visually attached to the step above
- markdown rendering should not leak raw JSON wrappers in normal flow
- fenced code blocks keep their block rendering

## Output Policy By `step_type`

| `step_type` | `output_format` | `visible_source` | `notes` |
|---|---|---|---|
| `notify` | `simple` | `text` | always simple |
| `shell` | `structured` | `value` | always structured |
| `wait_input` | `none` | `status_view` | prompt shown in global status, not transcript |
| `wait_webhook` | `none` | `status_view` | prompt shown in global status, not transcript |
| `wait_channel` | `none` | `status_view` | prompt shown in global status, not transcript |
| `switch` | `inline` | `value.next_step_id` | render as `[switch] step_id → next_step_id` |
| `when` | `inline` | `value.next_step_id` | render as `[when] step_id → next_step_id` |
| `send` | `simple` | `text` | compact result |
| `assign` | `pending` | `pending` | pending structure and shape |
| `agent` | `markdown + tool_lines` | `text` (+ tool command/result) | assistant text uses markdown; tool calls use muted `▪` lines |
| `mcp` | `pending` | `pending` | pending structure and shape |

## Final Status

The final line belongs to the run session block and closes it.

Target shape:

```text
  succeeded
```

Rules:
- use a simple user-facing status
- keep it visually lighter than the run header
- render it as the final state of the current run block, not as a standalone transcript message

## Errors

Runtime errors inside an existing run should belong to the run session block.

They should be concise and readable.

Target direction:

```text
↳ run(skill_name)
   created 018f78a1-8148-4948-9566-39f69a13692f
[step_type] step_id
  error:
   step failed
```

Rules:
- no raw traceback in the normal transcript
- the error should explain what failed in user terms
- the `error:` prefix should be explicit and stable
- runtime error stays inside the run block
- dispatch error stays outside the run block

## Waiting

When the run is waiting for input, the waiting state is represented in transcript by the wait placeholder (`...`) and in status view by `Waiting [prompt]`.

Target direction:

```text
   ...
```

Rules:
- the waiting state should be explicit
- the waiting prompt belongs to the global status view, not the transcript
- `waiting` is not rendered as a standalone transcript line

## Resume After Waiting Input

When the user types free text while the run is in `wait_input`, the run must resume in the same run session block.

Target direction:

```text
› /run wait_input_test

↳ run(wait_input_test)
   created 018f78a1-8148-4948-9566-39f69a13692f
   ...
› hola mundo
↳ resume(wait_input_test)
[notify] done
    hola mundo
  succeeded
```

Rules:
- the user reply line uses the normal user input styling
- the resume header is friendly (`resume(...)`) and stays in the same run session
- do not render transport/runtime technical events directly (for example `INPUT_RECEIVED` or raw `RUN_RESUME`)
- do not duplicate the same waiting step block after input is accepted unless the run enters a new waiting phase

## Full Example

```text
› /run skill_name

↳ run(skill_name)
   created 018f78a1-8148-4948-9566-39f69a13692f
[notify] show_message
    visible result
[shell] run_check
    {
      "value": {
        "exit_code": 0,
        "ok": true,
        "stderr": "",
        "stdout": ""
      }
    }
  succeeded
```

## Waiting Example

```text
› /run chat

↳ run(chat)
   created 018f78a1-8148-4948-9566-39f69a13692f
   ...
```

## Runtime Error Example

```text
› /run skill_name

↳ run(skill_name)
   created 018f78a1-8148-4948-9566-39f69a13692f
[shell] run_check
  error:
   command failed
```

## Next Direction

This visual spec should stay valid with the current `RichLog`-based transcript.

The implementation may evolve, but the transcript should keep:
- the same block structure
- the same compact reading flow
- the same distinction between command, run reply, step, output, and final status
