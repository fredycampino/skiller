# Done

## Status Board

| Area | Status | Notes |
| --- | --- | --- |
| Webhooks And Server | Done | Baseline server/webhook tooling is closed; only future UX and observability refinements remain. |
| Cloudflare Tunnel Tooling | Done | Moved to CLI/tooling form with `login`, `ensure`, `start`, `status`, and `stop`. |
| `shell` step v1 | Done | Implemented as the current runtime reference. |
| Large results / `body_ref` | Done | Implemented as the current persisted output reference. |

## Messaging Channels

| Item | Status | Notes |
| --- | --- | --- |
| Wait/event schema normalization | Done | `waits` and `external_events` now use `source_type`, `source_name`, `match_type`, and `match_key`. |
| Channel ingress in runtime | Done | `channel receive` and `wait_channel` are now first-class runtime primitives. |
| Channel outbound send step | Done | `send` now routes `channel + key + message` through a channel adapter and the WhatsApp bridge `POST /messages` endpoint. |
| Reuse existing runtime pieces | Done | Channel ingress reuses external-event persistence, wait lookup, worker resume, and runtime/UI observability. |
| Narrow inbound-first MVP | Done | Pairing, connection status, inbound capture, and resume of waiting runs are in place. |
| Bridge delivery model | Done | The WhatsApp bridge now pushes local channel events into the shared local server instead of relying on the old pull consumer loop. |
| Self-contained channel skills | Done | Run creation now blocks `wait_channel` / `wait_webhook` skills when the local server is unavailable, before `CreateRunUseCase.execute(...)`. |
| WhatsApp bridge availability guard | Done | Run creation now also blocks `wait_channel` / `send` WhatsApp skills when the WhatsApp bridge is not active. |

## Archive

- UI transcript moved to structured `events` only.

- TUI status polling no longer crashes if a persisted `body_ref` cannot be resolved; the UI now keeps the original output instead of failing the event loop.

- WhatsApp demo skills added:
  - `whatsapp_send_demo`
  - `whatsapp_drama`

- Webhooks and server baseline closed:
  - `server start|status|stop` done
  - `wait_webhook` runtime support done
  - remaining work is only future UX/observability polish

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
