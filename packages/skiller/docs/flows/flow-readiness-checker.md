# Flow Readiness Checker

## Goal

`FlowReadinessCheckerUseCase` loads a YAML flow definition and verifies whether required
local runtime services must already be available before run creation.

Current scope:
- `wait_channel`
- `wait_webhook`
- `send`

It depends on runtime state through:
- `ServerStatusPort.is_available()`
- `ChannelSenderPort.is_available(channel=...)`

## Invocation Order

Current `create_run(...)` flow:

```text
FlowCheckerUseCase.execute(flow_ref, flow_source=...)
FlowReadinessCheckerUseCase.execute(flow_ref, flow_source=...)
CreateRunUseCase.execute(skill_ref, inputs, skill_source=...)
AppendRuntimeEventUseCase.execute(run_id, event_type=RUN_CREATE, ...)
```

If `FlowReadinessCheckerUseCase` returns `INVALID`, run creation stops before `CreateRunUseCase.execute(...)`.

## Rule

The use case scans `steps` in declaration order.

If it finds a step with primary header:
- `wait_channel`
- `wait_webhook`

then the flow requires the local server.

If it finds a step with primary header:
- `wait_channel`
- `send`

and `channel=whatsapp`, then the flow also requires an active WhatsApp bridge.

If none of those conditions apply, the result is `VALID`.

If a server-requiring step exists:
- when `ServerStatusPort.is_available()` returns `true`, the result is `VALID`
- when `ServerStatusPort.is_available()` returns `false`, the result is `INVALID`

If a WhatsApp-requiring step exists:
- when `ChannelSenderPort.is_available(channel="whatsapp")` returns `true`, the result is `VALID`
- when it returns `false`, the result is `INVALID`

The current implementation reports only the first matching step for each requirement type.

## Result Contract

The checker returns `FLOW_*` error codes for flow readiness validation.

### Status

- `VALID`
- `INVALID`

### Error

```json
{
  "code": "FLOW_SERVER_UNAVAILABLE",
  "message": "FLOW_SERVER_UNAVAILABLE: flow requires local server for wait_channel (step=listen_whatsapp)"
}
```

For `wait_webhook`, the same code is used and the message changes the step type:

```text
FLOW_SERVER_UNAVAILABLE: flow requires local server for wait_webhook (step=listen_webhook)
```

For WhatsApp channel availability:

```json
{
  "code": "FLOW_WHATSAPP_UNAVAILABLE",
  "message": "FLOW_WHATSAPP_UNAVAILABLE: flow requires active WhatsApp bridge for send (step=reply)"
}
```

## Boundary

`FlowReadinessCheckerUseCase` does:
- load the flow definition
- inspect `steps`
- check whether the server is available
- check whether a required channel bridge is available

`FlowReadinessCheckerUseCase` does not:
- validate general flow structure
- start the server
- start the channel bridge
- create a run
- append runtime events
