# Backlog

## Status Board

| Area | Status | Next |
| --- | --- | --- |
| Messaging Channels | InProgress | Tighten end-to-end WhatsApp observability and close operator-facing outbound safety boundaries. |
| Skill Packaging | InProgress | Define grouped skill layout and colocated docs before changing the loader. |
| Persistence Refactor | InProgress | Split `SqliteStateStore` responsibilities into narrower stores. |
| UI Configuration | InProgress | Decide whether operator-facing LLM/API configuration belongs in the UI. |
| Packaging And Distribution | InProgress | Define install and publishing flow for `pip` / `pipx`. |
| Follow-Up Cleanup | InProgress | Refine transcript rendering and narrow the role of `/watch`. |
| Logs And Debug | InProgress | Decide how far `/logs` should go beyond the current raw/debug view. |
| `shell` Follow-Up | InProgress | Tighten long-term contract and safety boundaries for `shell`. |
| Time-Based Waiting | Todo | Add `wait_until` before exploring recurring schedules. |
| `agent.yml` Exploration | Todo | Validate whether a minimal agent layer fits the current runtime. |

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
| WhatsApp as first channel | InProgress | Inbound waits and basic outbound send now work; next close safety boundaries, richer observability, and channel UX polish. |
| Operator safety rules | Todo | Define allowlist, anti-echo, and reply boundaries before enabling any autonomous outbound behavior. |
| Channel observability polish | Todo | Decide what status/debug surface should expose bridge readiness, send timing, and outbound failures to operators. |
| Design references | Todo | Keep `docs-legacy/spike/whatsapp-gateway-flow.md`, `docs-legacy/spike/whatsapp-event-trigger-mvp.md`, `docs-legacy/spike/hermes-reusable-patterns.md`, and `docs-legacy/spike/whatsapp_sin_verificacion_negocio.md` as background references while refining the channel design. |

## Skill Packaging

| Item | Status | Next |
| --- | --- | --- |
| Filesystem schema | Todo | Define support for `skills/<name>.yaml`, `skills/<name>/skill.yaml`, and `skills/<group>/<name>/skill.yaml` plus colocated docs such as `README.md` and `flow.md`. |
| Resolution and compatibility | Todo | Define lookup order, whether `skill_ref` may contain `/`, migration from flat `skills/*.yaml`, and how grouped docs are linked. |

## Persistence Refactor

| Item | Status | Next |
| --- | --- | --- |
| Problem statement | Todo | Write down clearly that `SqliteStateStore` is growing across runs, runtime events, waits, external events, and webhook queries. |
| Extraction candidates | Todo | Explore `RunStore`, `RuntimeEventStore`, `WaitStore`, `ExternalEventStore`, and `WebhookQueryStore` as possible boundaries. |
| Extraction plan | Todo | Identify a safe extraction order that keeps the runtime stable while shrinking the current store. |
| Existing precedent | Todo | Run listing already moved to `RunQueryPort` / `SqliteRunQueryStore`; continue the split instead of widening `SqliteStateStore` again. |

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
| Recurring schedules | Todo | Do not explore `cron` or recurring scheduling until `wait_until` proves the one-shot model. |

## `agent.yml` Exploration

| Item | Status | Next |
| --- | --- | --- |
| Spike reference | Todo | Use `docs/spikes/agent-yml-v1.md` as the current design starting point. |
| Runtime viability | Todo | Study whether `agent.yml` should exist as a first-class runtime pattern rather than an ad hoc skill convention. |
| Thin first shape | Todo | Start with `wait_input`, `llm_prompt`, optional tool use, `notify`, and loop/finish behavior without growing into a full framework. |
| Missing prerequisites | Todo | Clarify history accumulation, repeated-turn state, interaction with `shell`, and the boundary between skill and agent runtime. |
| First implementation contract | Todo | If viable, define a minimal example, expected event flow, transcript shape, and first-cut constraints. |
