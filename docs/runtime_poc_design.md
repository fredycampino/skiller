# Agent Runtime POC (Python) — CLI + Webhooks + MCP + Skills

## Goal
Build a **minimal but correct** Agent-based application in Python that can:

- Run tasks from a **CLI**.
- Receive **webhooks** (external signals) and resume long-running workflows.
- Execute actions via **Tools**, including **MCP** tools.
- Load and run **Skills** (declarative workflows).
- Stay **LLM-provider agnostic** via a simple adapter interface.

> Core idea: **Agent = runtime (orchestrator) + tools + model + rules + state**  
> Application = agent + channels (CLI/webhooks) + infrastructure (DB, logs, deploy)

---

## Architecture (Layers)

### Application layer
- **CLI**: start runs, inspect status/logs, steer/cancel.
- **Webhook Receiver (FastAPI)**: receives `merge` / `publish` signals.
- **Event Bus**: `asyncio.Queue` for internal events.
- **State Store**: SQLite for runs, waits, and logs/events.

### Agent layer
- **Runtime / Orchestrator**: state machine + scheduler.
- **Skill Runner**: loads skill DSL (YAML/JSON) and executes steps.
- **Policy Gate**: allowlist, confirmations (optional), redaction.
- **Tool Router**: routes tool calls to implementations.
- **LLM Adapter**: OpenAI/Anthropic/Local interchangeable.

### Tools layer
- **MCP Client Tool**: `mcp.call(server, tool, args)`.
- **Internal Tools**: `wait_webhook`, `notify`, `set_context`, etc.

---

## Block Diagram (CLI + Webhooks)

```mermaid
flowchart LR
  subgraph APP[Application (POC)]
    CLI[CLI\n(run/status/logs/steer/cancel)] --> BUS[Event Bus\n(asyncio.Queue)]
    WHS[Webhook Server\n(FastAPI)] --> BUS
    STORE[(SQLite\nruns/waits/events/logs)] <--> RT
  end

  subgraph AG[Agent]
    RT[Runtime / Orchestrator\nState Machine + Scheduler]
    SK[Skill Runner\n(DSL -> Steps)]
    POL[Policy Gate]
    TR[Tool Router]
    LLM[LLM Adapter\n(OpenAI/Anthropic/Local)]
  end

  BUS --> RT
  RT --> SK
  RT <--> LLM
  RT --> POL --> TR

  subgraph TOOLS[Tools]
    MCP[MCP Client]
    INT[Internal Tools\nwait_webhook, notify]
  end
  TR --> MCP
  TR --> INT
```

---

## Runtime Proposal (Minimal, Production-shaped)

### Run statuses
- `CREATED`
- `RUNNING`
- `WAITING` (waiting for an external event)
- `SUCCEEDED`
- `FAILED`
- `CANCELLED`

### Runtime loop (event-driven)
- All external inputs become events:
  - `START_RUN`
  - `WEBHOOK_RECEIVED`
  - `STEER`
  - `CANCEL`
- The runtime **never blocks** waiting for webhooks.
- When a step needs a webhook signal, it creates a persisted **wait condition** and sets the run to `WAITING`.

### Key rule
**LLM never calls tools directly.**  
LLM ↔ Runtime only. Runtime → Tool Router → Tools.

---

## Skills (Declarative DSL)

### Design principles
- Skills are **data**, not code.
- A skill defines:
  - metadata + inputs
  - a list of `steps`
- Step types:
  - `tool` (invoke MCP or internal tool)
  - `wait_webhook` (persist wait condition; set `WAITING`)
  - `llm` (optional: generate text like PR description)
  - `notify` (user-facing notification)

### Example Skill — `create_release.yaml`
```yaml
name: create_release
inputs:
  repo: string
  base_branch: string
  release_branch: string
  pr_title: string
  publish_target: string

steps:
  - id: create_branch
    type: tool
    tool: mcp.git.create_branch
    args:
      repo: "{{inputs.repo}}"
      from: "{{inputs.base_branch}}"
      name: "{{inputs.release_branch}}"

  - id: create_pr
    type: tool
    tool: mcp.git.create_pr
    args:
      repo: "{{inputs.repo}}"
      head: "{{inputs.release_branch}}"
      base: "{{inputs.base_branch}}"
      title: "{{inputs.pr_title}}"

  - id: wait_merge
    type: wait_webhook
    wait_key: "webhook.merge.xyz"
    match:
      repo: "{{inputs.repo}}"
      branch: "{{inputs.release_branch}}"

  - id: publish
    type: tool
    tool: mcp.release.publish_xyz
    args:
      repo: "{{inputs.repo}}"
      target: "{{inputs.publish_target}}"

  - id: wait_publish_confirm
    type: wait_webhook
    wait_key: "webhook.publish.abc"
    match:
      repo: "{{inputs.repo}}"
      target: "{{inputs.publish_target}}"

  - id: notify_done
    type: notify
    message: "Release completed: {{inputs.repo}} ({{inputs.release_branch}})"
```

---

## Tools

### MCP tool (adapter)
**Generic** interface:
- `mcp.call(server: str, tool: str, args: dict) -> dict`

Then you can expose friendly names:
- `mcp.git.create_branch`
- `mcp.git.create_pr`
- `mcp.release.publish_xyz`

### Internal tools (POC)
- `wait_webhook(wait_key, match)`: persists wait condition and sets run `WAITING`.
- `notify(message)`: prints/logs and stores a notification event.
- `set_context(key, value)`: stores structured state for later steps.

---

## Webhooks: Receiver + Matching

### Webhook receiver (FastAPI)
- Receives `POST /webhooks/{key}` with JSON payload.
- Emits event: `WEBHOOK_RECEIVED(key, payload)` to the event bus.
- Runtime checks all waits with matching `wait_key` and validates `match` filter.

### Wait condition matching
- `wait_key`: string namespace, e.g. `webhook.merge.xyz`
- `match`: JSON dict of fields that must match payload (simple equals comparison)

> POC matching is kept intentionally simple. Later you can add JSONPath/JMESPath.

---

## Minimal Data Model (SQLite)

### `runs`
- `id` (uuid)
- `skill_name` (text)
- `status` (text)
- `current_step` (int)
- `context_json` (text)
- `created_at`, `updated_at`

### `waits`
- `id` (uuid)
- `run_id` (uuid)
- `wait_key` (text)
- `match_json` (text)
- `status` (text: ACTIVE/RESOLVED/EXPIRED)
- `created_at`, `expires_at` (optional)

### `events` (optional but recommended)
- `id` (uuid)
- `run_id` (uuid nullable)
- `type` (text)
- `payload_json` (text)
- `created_at`

---

## CLI Commands (POC)
- `agent run <skill> --arg value ...`
- `agent status <run_id>`
- `agent logs <run_id>`
- `agent steer <run_id> "<message>"`
- `agent cancel <run_id>`

**Testing helper (no tunnel needed):**
- `agent webhook inject <wait_key> --json payload.json`

---

## Cloudflare Tunnel (for real webhooks)
To receive webhooks on a local FastAPI server, expose it via a tunnel.

Two POC modes:
1. **Simulated webhooks** via `agent webhook inject ...` (fastest start)
2. **Real webhooks** via Cloudflare Tunnel (more realistic)

> Tunnel setup details are implementation work; the design assumes the webhook receiver has a public URL.

---

## Execution Flow — Create a release
1. `CLI` starts run → `START_RUN`
2. Runtime executes:
   - create branch (MCP)
   - create PR (MCP)
3. Runtime hits `wait_merge`:
   - persists wait
   - run becomes `WAITING`
4. Webhook `merge.xyz` arrives:
   - `WEBHOOK_RECEIVED` event emitted
   - runtime matches wait and resumes
5. Runtime executes publish (MCP)
6. Wait `publish.abc` → `WAITING`
7. Webhook `abc` arrives → resume → notify → `SUCCEEDED`

---

## What we refine before implementing
- Exact webhook payload shape for `merge.xyz` and `publish.abc`
- Naming and error semantics of MCP tools (idempotency, retries)
- Policy Gate: allowlist per skill, max steps, timeouts
- Minimal logs/traces format (human-readable + JSON)

---
