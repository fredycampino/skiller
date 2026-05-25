# TUI Transcript Visual Spec

## Goal

Define the current TUI transcript contract.

This document describes what transcript items exist, how runtime events are projected
into those items, and how each item is expected to render.

It does not define polling internals.

## Rendering Pipeline

Current path:

```text
runtime event -> EventTranscriptMapper -> TranscriptItem
TranscriptItem -> ProjectTranscriptUseCase -> TranscriptView -> Rich renderable
```

The viewmodel can also append transcript items directly, for example user input,
run acknowledgments, resume acknowledgments, intro/info messages, and dispatch errors.

Rules:
- one transcript item maps to one transcript view
- output views use a prefix column plus content column
- transcript content must not expose raw runtime event names
- transcript content must prefer user-facing text over transport payloads

## Modes

Default mode is `CHAT`.

`ProjectTranscriptUseCase` is the only projection point that currently diverges by mode.

`FLOW`:
- shows all transcript items

`CHAT`:
- hides `RunResumeItem`
- hides `RunStepItem` when `step_type` is `switch` or `when`
- hides `RunOutputItem`, `StepNotifyOutputItem`, `StepOutputItem`, and
  `StepShellOutputItem` when `step_type` is `switch` or `when`

No command changes the mode today.

## Transcript Items

Current item set:

| Item | Responsibility |
|---|---|
| `UserInputItem` | user command or free-text input |
| `InfoItem` | local TUI informational message |
| `DispatchErrorItem` | error before a run session exists |
| `RunAckItem` | local acknowledgment that a run was started |
| `RunResumeItem` | local acknowledgment that a waiting run was resumed |
| `RunStepItem` | visible step header or wait placeholder |
| `AgentToolCallItem` | agent tool command line |
| `AgentToolResultItem` | agent tool result preview |
| `AgentAssistantMessageItem` | non-final assistant message inside an agent step |
| `AgentFinalAssistantMessageItem` | final assistant event marker; renders blank today |
| `AgentStepFinalOutputItem` | visible final agent answer from `STEP_SUCCESS + agent` |
| `AgentSystemNoticeItem` | agent interrupted / max turns exhausted notice |
| `RunOutputItem` | legacy generic run output view |
| `StepNotifyOutputItem` | `notify` step output |
| `StepShellOutputItem` | `shell` step output |
| `StepOutputItem` | generic non-agent, non-notify, non-shell step output |
| `StepErrorItem` | step-level error detail |
| `RunFinishedItem` | final muted run status line |
| `RunWaitingInputItem` | wait placeholder plus status prompt source |
| `RunWaitingWebhookItem` | webhook wait data for visible marker |

## Event Mapping

`EventTranscriptMapper` maps events as follows:

| Event | Item |
|---|---|
| `RUN_CREATE` | none |
| `RUN_RESUME` | none |
| `INPUT_RECEIVED` | `UserInputItem` |
| `AGENT_ASSISTANT_MESSAGE` | `AgentAssistantMessageItem` |
| `AGENT_FINAL_ASSISTANT_MESSAGE` | `AgentFinalAssistantMessageItem` |
| `AGENT_TOOL_CALL` | `AgentToolCallItem` |
| `AGENT_TOOL_RESULT` | `AgentToolResultItem` |
| `AGENT_INTERRUPTED` | `AgentSystemNoticeItem` |
| `AGENT_MAX_TURNS_EXHAUSTED` | `AgentSystemNoticeItem` |
| `STEP_STARTED + wait_input` | none |
| `STEP_STARTED + wait_webhook` | none |
| `STEP_STARTED + other` | `RunStepItem` |
| `STEP_SUCCESS + agent` | `AgentStepFinalOutputItem` |
| `STEP_SUCCESS + wait_input` | none |
| `STEP_SUCCESS + notify` | `StepNotifyOutputItem` |
| `STEP_SUCCESS + shell` | `StepShellOutputItem` |
| `STEP_SUCCESS + other` | `StepOutputItem` |
| `STEP_ERROR` | `StepErrorItem` |
| `OBSERVER_LOOP_ERROR` | `DispatchErrorItem` |
| `RUN_WAITING + wait_input` | `RunWaitingInputItem` |
| `RUN_WAITING + wait_webhook` | `RunWaitingWebhookItem` |
| `RUN_WAITING + other` | none |
| `RUN_FINISHED` | `RunFinishedItem` |

Important details:
- `RunAckItem` and `RunResumeItem` are local viewmodel items, not direct log-event mappings.
- `AgentFinalAssistantMessageItem` currently renders a blank line. The visible final agent
  answer is `AgentStepFinalOutputItem`.
- agent usage for the footer comes from `AgentStepFinalOutputItem.usage`.
- `RUN_FINISHED` does not render error detail. Step failure detail belongs to `StepErrorItem`.

## General Layout

User input:

```text
› /run onboarding
```

Run acknowledgment:

```text
↳ run(onboarding)
   created 018f78a1-8148-4948-9566-39f69a13692f
```

Run resume:

```text
↳ resume(onboarding)
```

Dispatch error:

```text
error:
  agent not found: onboarding
```

Rules:
- do not render `run(...)` when run creation failed
- do not expose tracebacks in the normal transcript
- keep the transcript compact and scan-friendly

## Step Headers

Regular visible step:

```text
[shell] create_config
```

Wait placeholder:

```text
   ...
```

Rules:
- `RunStepView` renders `[step_type] step_id`
- wait step types render the muted placeholder instead of `[wait_*] step_id`
- wait step types are `wait_input`, `wait_webhook`, and `wait_channel`
- `STEP_STARTED + wait_input` is hidden; the placeholder for input waits comes from
  `RUN_WAITING + wait_input`
- `STEP_STARTED + wait_webhook` is hidden; the webhook wait marker comes from
  `RUN_WAITING + wait_webhook`
- `RUN_WAITING` for waits other than input and webhook is hidden today

## Message Output Views

`StepNotifyOutputView`, `StepShellOutputView`, `StepOutputView`, `StepErrorView`, and
agent message views use the same visual pattern:

```text
<icon> <content>
```

The icon lives in a fixed prefix column and content lives in the next column.

### Notify Output

`STEP_SUCCESS + notify` renders `StepNotifyOutputItem`.

```text
• Choose an AI provider for agent steps.
  Available now: minimax.
```

Rules:
- icon is `•`
- format comes from `NotifyOutputValue.format`
- supported formats are `simple`, `markdown`, and `structured`
- default notify format is `simple`
- content comes from `NotifyOutputValue.message`
- the latest notify output is primary
- older notify outputs are muted
- if `RunWaitingInputItem` is the last item, the notify immediately before it remains primary

### Shell Output

`STEP_SUCCESS + shell` renders `StepShellOutputItem`.

```text
▫ Config: /home/fede/.skiller/settings/agent.json
  Secret: /home/fede/.skiller/secrets/minimax_api_key
```

Rules:
- icon is `▫`
- output format is `simple`
- render stdout/stderr joined when either exists
- fall back to `output.text` when stdout and stderr are empty
- do not render the shell command
- do not render a `$` prefix
- do not render the raw JSON result when readable stdout/stderr text exists
- the latest shell output is primary
- older shell outputs are muted
- if `RunWaitingInputItem` is the last item, the shell output immediately before it remains primary

### Generic Step Output

`STEP_SUCCESS` for non-agent, non-wait-input, non-notify, non-shell steps renders
`StepOutputItem`.

```text
⇢ assigned values.
```

Icon mapping:

| `step_type` | icon |
|---|---|
| `assign` | `⇢` |
| `mcp` | `@` |
| `send` | `>` |
| `switch` | `↳` |
| `wait_channel` | `#` |
| `wait_webhook` | `~` |
| `when` | `↳` |
| other | `•` |

Rules:
- output format is `simple` except `agent`, which is handled separately as markdown
- `switch` and `when` output text is the selected `next_step_id` plus `.`
- the latest generic step output is primary
- older generic step outputs are muted
- if `RunWaitingInputItem` is the last item, the step output immediately before it remains primary

## Agent Step

An agent step is one visual block.

Example:

```text
[agent] support_agent
‹ I will inspect the repository state.
  ▪ $ git status --short
      M src/...

‹ Done. The issue was in the mapper.
```

Rules:
- `RunStepItem(step_type="agent")` renders the `[agent] step_id` header
- `AgentAssistantMessageItem` renders assistant prose with the `‹` prefix
- `AgentToolCallItem` renders muted tool command lines with the `▪` marker
- `AgentToolResultItem` renders muted preview text under the tool call
- the latest tool call stays active while it is the last tool-related item
- `AgentFinalAssistantMessageItem` renders blank today
- `AgentStepFinalOutputItem` renders the visible final answer with the `‹` prefix
- `AgentStepFinalOutputItem.usage` is the source for footer usage state

Agent system notices:

```text
! Interrupted by user
! Turn limit reached
```

Rules:
- interrupted and max-turns-exhausted notices use `AgentSystemNoticeItem`
- notices use warning style
- notices do not use the `‹` assistant prefix
- final agent output is still shown if the runtime emits `STEP_SUCCESS + agent`

## Waiting

Input wait transcript:

```text
   ...
```

Status view:

```text
Waiting [Select your AI provider. Type: minimax or exit]
```

Rules:
- transcript only shows the placeholder
- the prompt belongs to status view
- `STEP_SUCCESS + wait_input` renders nothing
- `RUN_WAITING + wait_input` creates `RunWaitingInputItem`
- `RUN_WAITING + wait_webhook` creates `RunWaitingWebhookItem`

Webhook wait transcript:

```text
↯ Waiting webhook:
  example-auth/GrbyVerTlIkPm33R-DbTe_7h3WKNbKkl
```

Rules:
- icon is `↯`
- mapper stores `webhook` and `key`
- visible label comes from `TuiStrings.waiting_webhook_message`
- view renders `<label>:` and `<webhook>/<key>` on the next line
- view has top padding
- if it is the latest transcript item, text uses warning color
- otherwise text uses muted color
- status view stays generic and shows `...`

## Errors

Step errors render as `StepErrorItem`.

```text
× shell command path escapes workspace
```

Rules:
- icon is `×`
- message is rendered in error color
- no `error:` wrapper is added for step errors
- `RunFinishedItem(status="error")` still renders the final muted `failed` line

Dispatch errors still use the dispatch error block:

```text
error:
  skill not found: onboarding
```

## Final Run Status

`RUN_FINISHED` renders `RunFinishedItem`.

Succeeded:

```text
  succeeded
```

Failed:

```text
  failed
```

Rules:
- final status is muted
- status text is only `succeeded` or `failed`
- failure detail belongs to `StepErrorItem`, not the final status line

## Full Example

```text
› /run onboarding

↳ run(onboarding)
   created 018f78a1-8148-4948-9566-39f69a13692f
[shell] intro
▫ Welcome
[notify] provider_options
• Choose an AI provider for agent steps.
  Available now: minimax.
   ...
› ok
[agent] verify_minimax
‹ I will verify the provider.

‹ MiniMax responded. Agent configuration is ready.
  succeeded
```

## Failure Example

```text
› /run onboarding

↳ run(onboarding)
   created 018f78a1-8148-4948-9566-39f69a13692f
[agent] verify_minimax
× Agent 'verify_minimax' LLM request failed: request failed
  failed
```
