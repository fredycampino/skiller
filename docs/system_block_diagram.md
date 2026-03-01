# System Block Diagram

```mermaid
flowchart LR
  subgraph APP[Application Layer]
    CLI[CLI<br/>run/status/logs/steer/cancel]
    WH[Webhook Receiver<br/>FastAPI POST /webhooks/{key}]
    BUS[Event Bus<br/>asyncio.Queue]
    DB[(SQLite<br/>runs / waits / events)]
  end

  subgraph AGENT[Agent Layer]
    RT[Runtime / Orchestrator<br/>State machine + scheduler]
    SK[Skill Runner<br/>DSL YAML/JSON -> steps]
    PG[Policy Gate<br/>allowlist / limits / confirmations]
    TR[Tool Router]
    LLM[LLM Adapter<br/>OpenAI / Anthropic / Local]
  end

  subgraph TOOLS[Tools Layer]
    MCP[MCP Client<br/>mcp.call(server, tool, args)]
    INT[Internal Tools<br/>wait_webhook, notify, set_context]
  end

  CLI --> BUS
  WH --> BUS
  BUS --> RT
  RT --> SK
  RT <--> LLM
  RT --> PG --> TR
  TR --> MCP
  TR --> INT
  RT <--> DB
  WH --> DB

  classDef ext fill:#f6f6f6,stroke:#777,stroke-width:1px;
  class LLM,MCP ext;
```

## Main flow

1. CLI starts a run and emits `START_RUN`.
2. Runtime executes skill steps through `Tool Router`.
3. A `wait_webhook` step persists an active wait in SQLite and sets status to `WAITING`.
4. Webhook receiver emits `WEBHOOK_RECEIVED` into the Event Bus.
5. Runtime matches wait conditions, resumes execution, and completes with `SUCCEEDED` or `FAILED`.
6. All transitions are stored as events/logs for observability.
