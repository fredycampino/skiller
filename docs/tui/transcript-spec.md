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
- `RUN_STEP`
- `RUN_OUTPUT`
- `RUN_STATUS`
- `INFO`

Notes:
- `DISPATCH_ERROR` is outside the run session block because no run was created
- `RUN_STATUS` belongs to the run session block
- `RUN_STATUS` covers states such as `waiting`, `succeeded`, and `error`

## Principles

- The transcript is a console transcript, not a chat transcript.
- It must feel operational and compact.
- It must not expose raw runtime event names to the user.
- It must not expose transport details from polling or CLI integration.
- It must prefer readable output over debug output.

## General Layout

- The user command appears exactly as entered.
- The run reply appears as a separate visual block.
- Each run reply is a run session block.
- There is one blank line between the user command and the run block.
- Inside a run block there are no extra blank lines.
- The transcript must be easy to scan top to bottom.

Example:

```text
/run notify_test

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

Show the command exactly as entered.

Example:

```text
/run delay_test
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

## Output Policy By `step_type`

| `step_type` | `output_format` | `visible_source` | `notes` |
|---|---|---|---|
| `notify` | `simple` | `text` | always simple |
| `shell` | `structured` | `value` | always structured |
| `wait_input` | `simple` | `text` | prompt visible |
| `wait_webhook` | `simple` | `text` | waiting prompt visible |
| `wait_channel` | `simple` | `text` | waiting prompt visible |
| `llm_prompt` | `simple` | `text` | multiline allowed |
| `switch` | `simple` | `text` | compact result |
| `when` | `simple` | `text` | compact result |
| `send` | `simple` | `text` | compact result |
| `assign` | `pending` | `pending` | pending structure and shape |
| `agent` | `pending` | `pending` | pending structure and shape |
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

When the run is waiting for input, the waiting state belongs to the run session block.

The transcript should show the waiting prompt in a readable way.

Target direction:

```text
  waiting
  Write a message. Type exit, quit, or bye to stop.
```

Rules:
- the waiting state should be explicit
- the prompt should read like a next action for the user
- waiting is the current state of the run block, not a standalone transcript message

## Full Example

```text
/run skill_name

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
/run chat

↳ run(chat)
   created 018f78a1-8148-4948-9566-39f69a13692f
   [wait_input] ask_user
    Write a message. Type exit, quit, or bye to stop.
  waiting
```

## Runtime Error Example

```text
/run skill_name

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
