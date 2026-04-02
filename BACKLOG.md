# Backlog

## Status Board

| Area | Status | Next |
| --- | --- | --- |
| Webhooks And Server | Done | Baseline server/webhook tooling is closed; only future UX and observability refinements remain. |
| Messaging Channels | Active | Define WhatsApp as the first inbound channel on top of existing wait/webhook runtime pieces. |
| Skill Packaging | Active | Define grouped skill layout and colocated docs before changing the loader. |
| Persistence Refactor | Active | Split `SqliteStateStore` responsibilities into narrower stores. |
| UI Configuration | Active | Decide whether operator-facing LLM/API configuration belongs in the UI. |
| Packaging And Distribution | Active | Define install and publishing flow for `pip` / `pipx`. |
| Follow-Up Cleanup | Active | Refine transcript rendering and narrow the role of `/watch`. |
| Logs And Debug | Active | Decide how far `/logs` should go beyond the current raw/debug view. |
| `shell` Follow-Up | Active | Tighten long-term contract and safety boundaries for `shell`. |
| Time-Based Waiting | Planned | Add `wait_until` before exploring recurring schedules. |
| `agent.yml` Exploration | Planned | Validate whether a minimal agent layer fits the current runtime. |
| Cloudflare Tunnel Tooling | Done | Moved to CLI/tooling form with `login`, `ensure`, `start`, `status`, and `stop`. |
| `shell` step v1 | Done | Implemented as the current runtime reference. |
| Large results / `body_ref` | Done | Implemented as the current persisted output reference. |

## Webhooks And Server

| Item | Status | Next |
| --- | --- | --- |
| Local server tooling | Done | `server start|status|stop` now uses explicit Skiller ownership under `~/.skiller/webhooks` and reports `managed_by_skiller`. |
| Webhook runtime support | Done | `wait_webhook`, webhook registry, local server lifecycle, and CLI/UI observability are already in place. |
| Remaining follow-up | Deferred | Handle only as future UX/observability polish, not as an open tooling gap. |

## Follow-Up Cleanup

| Item | Status | Next |
| --- | --- | --- |
| CLI `/watch` stderr output | Todo | Decide whether compact event text still belongs on `stderr` now that the UI consumes structured `events`. |
| Transcript create/resume rendering | Todo | Decide whether `RUN_CREATE` and `RUN_RESUME` need more explicit transcript treatment beyond the block header. |
| Step result rendering in the UI | Todo | Define compact vs expanded rendering, truncation/body-ref behavior, and whether some step types need custom views. |
| `/watch <run_id>` product role | Todo | Reframe `/watch` as reattach/stream-new-events if that is the intended long-term contract, then align help and docs. |

## Logs And Debug

| Item | Status | Next |
| --- | --- | --- |
| `/logs` follow-up | Todo | Decide whether to add `--tail`, event-type filtering, or JSON-only formatting on top of the current raw/debug view. |

## Messaging Channels

| Item | Status | Next |
| --- | --- | --- |
| Reuse existing runtime pieces | Defined | Build on top of `wait_webhook`, inbound webhook handling, local server lifecycle, worker resume flows, runtime events, and current UI/CLI observability. |
| WhatsApp as first inbound channel | Todo | Define it as a channel adapter with bridge/session lifecycle, local ownership, and mapping onto the existing wait/webhook path where possible. |
| Narrow inbound-first MVP | Todo | Limit v1 to pairing, connection status, inbound capture, and resume of waiting runs; defer new-run creation unless the existing path is not enough. |
| Operator safety rules | Todo | Define allowlist, anti-echo, and reply boundaries before enabling any autonomous outbound behavior. |
| Design references | Defined | `docs-legacy/spike/whatsapp-gateway-flow.md`, `docs-legacy/spike/hermes-reusable-patterns.md`, `docs-legacy/spike/whatsapp_sin_verificacion_negocio.md`. |

## Skill Packaging

| Item | Status | Next |
| --- | --- | --- |
| Filesystem schema | Todo | Define support for `skills/<name>.yaml`, `skills/<name>/skill.yaml`, and `skills/<group>/<name>/skill.yaml` plus colocated docs such as `README.md` and `flow.md`. |
| Resolution and compatibility | Todo | Define lookup order, whether `skill_ref` may contain `/`, migration from flat `skills/*.yaml`, and how grouped docs are linked. |

## Persistence Refactor

| Item | Status | Next |
| --- | --- | --- |
| Problem statement | Todo | Write down clearly that `SqliteStateStore` is growing across runs, runtime events, waits, external events, and webhook queries. |
| Extraction candidates | Defined | Explore `RunStore`, `RuntimeEventStore`, `WaitStore`, `ExternalEventStore`, and `WebhookQueryStore` as possible boundaries. |
| Extraction plan | Todo | Identify a safe extraction order that keeps the runtime stable while shrinking the current store. |
| Existing precedent | Defined | Run listing already moved to `RunQueryPort` / `SqliteRunQueryStore`; continue the split instead of widening `SqliteStateStore` again. |

## UI Configuration

| Item | Status | Next |
| --- | --- | --- |
| LLM/API configuration in the UI | Todo | Decide whether the UI should expose operator flows for API key, endpoint, local persistence vs env-backed config, and visibility of missing credentials without overstepping secret-management boundaries. |

## Packaging And Distribution

| Item | Status | Next |
| --- | --- | --- |
| Install and publish flow | Todo | Validate the package name, `pip` / `pipx` install story, release-driven publishing workflow, installation docs, and first-run operator defaults. |

## `shell` Follow-Up

| Item | Status | Next |
| --- | --- | --- |
| Long-term command model | Todo | Decide whether `shell` stays shell-only or later splits into structured `command/argv` plus interpreter selection. |
| Safety boundary review | Todo | Revisit quoting, environment inheritance, timeouts, and large-output truncation. |
| Future extensions | Todo | Decide whether `shell` should add interpreter override, no-shell execution mode, or stronger sandbox/policy integration. |

## Time-Based Waiting

| Item | Status | Next |
| --- | --- | --- |
| `wait_until` primitive | Todo | Persist a run in `WAITING` with `wait_type = time`, store a due timestamp, and resume when it is reached. |
| Recurring schedules | Deferred | Do not explore `cron` or recurring scheduling until `wait_until` proves the one-shot model. |

## `agent.yml` Exploration

| Item | Status | Next |
| --- | --- | --- |
| Spike reference | Defined | `docs/spikes/agent-yml-v1.md` is the current design starting point. |
| Runtime viability | Planned | Study whether `agent.yml` should exist as a first-class runtime pattern rather than an ad hoc skill convention. |
| Thin first shape | Planned | Start with `wait_input`, `llm_prompt`, optional tool use, `notify`, and loop/finish behavior without growing into a full framework. |
| Missing prerequisites | Planned | Clarify history accumulation, repeated-turn state, interaction with `shell`, and the boundary between skill and agent runtime. |
| First implementation contract | Planned | If viable, define a minimal example, expected event flow, transcript shape, and first-cut constraints. |

## DONE

- UI transcript moved to structured `events` only.

- Removed `events_text` fallback and raw watch text parsing from the TUI path.

- `/logs` defined as raw/debug output and rendered as pretty JSON in the TUI.

- Run listing moved onto a dedicated read side:
  - `RunQueryPort`
  - `SqliteRunQueryStore`
  - `RunListItem`
  - `StateStorePort` no longer owns `list_runs`

- `/runs` became the single waiting view instead of adding more wait-specific commands:
  - waiting runs surface `wait_type`
  - webhook waits surface `wait_detail`
  - UI supports `/runs waiting`
  - file-based skills render by basename in the runs view

- Transcript headers standardized as:
  - `[run-create] skill:id4`
  - `[run-resume] skill:id4`

- Transcript step format standardized as:
  - `[step_type] step_id`

- Transcript became incremental by `event_id`, including create/resume block handling.

- TUI `/run` now follows runs incrementally instead of staying on the initial snapshot:
  - CLI `run --detach`
  - UI-side status + logs polling
  - delayed verification skill `ui_progress_test`

- Output wrapping improved:
  - preserved indentation on wrapped lines
  - wrapped long detail text by word instead of breaking inside words

- Status bar simplified to:
  - `Waiting → input`
  - `Waiting → webhook`

- Runtime event contract completed and adopted:
  - `RUN_CREATE`
  - `RUN_RESUME`
  - `STEP_STARTED`
  - `STEP_SUCCESS`
  - `STEP_ERROR`
  - `RUN_WAITING`
  - `RUN_FINISHED`

- `run.context.step_executions` became the persisted source of truth for runtime state.

- Runtime step execution model aligned in one cut:
  - `RunContext.step_executions`
  - `StepExecution`
  - typed `*Output` objects per step
  - normalized public `event.payload.output`

- `shell` step added in v1:
  - `command`, `cwd`, `env`, `timeout`, `check`, `large_result`
  - runtime shell resolution via `$SHELL`, `/bin/bash`, `/bin/sh`
  - `ShellOutput` with `ok`, `exit_code`, `stdout`, `stderr`
  - unit, integration, and CLI e2e coverage

- Webhooks and server support completed in v1:
  - `skiller run --start-server`
  - `skiller server start`
  - `skiller server status`
  - `skiller server stop`
  - `skiller webhook register`
  - `skiller webhook list`
  - `skiller webhook remove`
  - `skiller webhook receive`
  - `/server status`
  - `/webhooks`
  - `wait_webhook`

- Large results support added:
  - persisted `execution_outputs`
  - `event.payload.output.body_ref`
  - optional `text_ref` for rebuilding full human text from stored bodies
  - `large_result: true` support in `mcp` and `llm_prompt`
  - UI body resolution via `/body` and transcript/status/log body loading

- Legacy runtime result contract removed:
  - no `run.context.results`
  - no `event.payload.result`
  - no `*Result` dataclasses by step

- State rehydration from observability events was removed.

- `webhook_registrations` ownership moved out of the state store and into `SqliteWebhookRegistry`.

- Wait persistence unified into a single `waits` table with `wait_type`.

- External resume payload storage unified into a single `external_events` table with `event_type`.

- `docs/db/schema.md` created and aligned with the current schema.

- Skill entrypoint made explicit with root `start: <step_id>`.

- Skill step syntax simplified to:
  - `- <step_type>: <step_id>`

- Hidden YAML conventions removed from authoring:
  - no mandatory `id: start`
  - no `id`
  - no `type`

- MCP step contract aligned with compact syntax:
  - step header `- mcp: <step_id>`
  - server field `server: <mcp_server_name>`

- Skills, e2e fixtures, integration fixtures, and step docs migrated to the new skill syntax.

- CLI command guide added and linked from `README.md`.

- Runtime/UI transcript behavior docs added and aligned:
  - `run_transcript.md`
  - `logs_debug.md`
  - related UI behavior docs

- Cloudflare tunnel tooling moved to CLI/tooling form:
  - `cloudflared login start|status|stop`
  - `cloudflared ensure --domain <domain>`
  - `cloudflared start|status|stop`
  - support for `SKILLER_DEBUG_HOME`
  - local managed state under `~/.skiller/cloudflared/*.json`
  - distinct login state and managed connector ownership
  - generated tunnel config at `~/.cloudflared/skillerwh-config.yml`
  - tunnel token fallback when local credentials JSON is missing
  - DNS `already exists` validation against the expected tunnel target
  - public hostname publishing via tunnel config `ingress`
  - local stop only; remote delete and DNS cleanup remain manual-by-design
  - dedicated CLI docs

- Local server tooling hardened:
  - managed state moved under `~/.skiller/webhooks/*.json`
  - `managed_by_skiller` exposed in CLI output
  - stale/reused PID protection before stop
  - dedicated CLI docs

- Initial messaging/channel design spikes added:
  - `whatsapp-gateway-flow.md`
  - `hermes-reusable-patterns.md`
  - `whatsapp_sin_verificacion_negocio.md`
