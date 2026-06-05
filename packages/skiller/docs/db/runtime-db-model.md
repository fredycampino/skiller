# Runtime DB Model (SQLite v6)

This document explains the runtime database model at a high level. For the table columns and
indexes, see [`schema.md`](schema.md).

## Purpose

The runtime database stores the state needed to resume, inspect, and continue Skiller runs.

It is not one single event log. It has separate responsibilities:

| Area | Tables | Purpose |
| --- | --- | --- |
| Run state | `runs` | Current state of a run. |
| Runtime history | `log_events` | Ordered events for logs, watch, and UI consumers. |
| External input | `waits`, `external_events`, `external_receipts`, `webhook_registrations` | Wait registration, external payloads, deduplication, and webhook configuration. |
| Agent memory | `agent_context_entries` | Agent conversation context and context-window markers. |

The most important split is:
- `runs` answers "where is this run now?"
- `log_events` answers "what happened over time?"
- `agent_context_entries` answers "what does the agent remember?"

## Versioning

The runtime DB version is `6`.

Skiller stores the version with SQLite `PRAGMA user_version`. When the runtime starts:
- an empty DB is initialized as the current version
- a non-empty DB with a different version is rejected

This keeps the runtime contract explicit. There is no silent compatibility mode for old schemas.

## Run State

The `runs` table is the current state of a run.

It owns:
- the flow reference and flow snapshot used to create the run
- lifecycle status
- current step
- initial inputs
- latest output for each executed step
- attached agent context ids
- steering queue
- cancellation state

`step_executions_json` is a state map, not a history. It is indexed by `step_id`, so a loop that
executes the same step multiple times keeps the latest execution for that step.

Historical step activity belongs to `log_events`.

## Runtime History

`log_events` is the chronological stream of runtime activity.

It is used by:
- `skiller logs`
- `skiller watch`
- UI transcripts
- runtime event consumers

Events are sequenced per run. They can carry step metadata and, for agent events, an agent context
sequence.

Consumers should read `log_events` when they care about order. They should read `runs` when they care
about the latest state.

## Waits And External Input

Skiller persists waits and external events separately.

`waits` stores what the runtime is waiting for.

`external_events` stores incoming payloads that may satisfy a wait.

`external_receipts` stores deduplication receipts, so repeated external deliveries are not accepted
twice.

`webhook_registrations` stores global webhook channel configuration. It is not owned by any specific
run.

Wait matching is normalized around:
- `source_type`
- `source_name`
- `match_type`
- `match_key`

This lets manual input, webhooks, and channels use the same matching machinery.

## Agent Memory

`agent_context_entries` stores agent context independently from the runtime event stream.

It contains:
- user messages
- assistant messages
- tool calls
- tool results

The context has its own `sequence` per `context_id`. That sequence is not the same as
`log_events.sequence`.

Measured assistant messages can carry token markers:
- `delta_tokens`
- `window_start_sequence`
- `window_base`
- `usage_json`

`delta_tokens` is the prompt-token delta attributed to that measured response. The active
window start is stored in the run's agent state and copied to measured entries for diagnostics.

## Deletion Boundary

Deleting a run removes data owned by that run:
- run row
- runtime events
- waits
- external events tied to the run
- deduplication receipts linked to those external events
- agent context entries for the run

Webhook registrations are global configuration and are not removed by run deletion.
