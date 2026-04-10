# Skill Server Checker

## Goal

`SkillServerCheckerUseCase` loads a skill and verifies whether required local runtime services must already be available before run creation.

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
SkillCheckerUseCase.execute(skill_ref, skill_source=...)
SkillServerCheckerUseCase.execute(skill_ref, skill_source=...)
CreateRunUseCase.execute(skill_ref, inputs, skill_source=...)
AppendRuntimeEventUseCase.execute(run_id, event_type=RUN_CREATE, ...)
```

If `SkillServerCheckerUseCase` returns `INVALID`, run creation stops before `CreateRunUseCase.execute(...)`.

## Rule

The use case scans `steps` in declaration order.

If it finds a step with primary header:
- `wait_channel`
- `wait_webhook`

then the skill requires the local server.

If it finds a step with primary header:
- `wait_channel`
- `send`

and `channel=whatsapp`, then the skill also requires an active WhatsApp bridge.

If none of those conditions apply, the result is `VALID`.

If a server-requiring step exists:
- when `ServerStatusPort.is_available()` returns `true`, the result is `VALID`
- when `ServerStatusPort.is_available()` returns `false`, the result is `INVALID`

If a WhatsApp-requiring step exists:
- when `ChannelSenderPort.is_available(channel="whatsapp")` returns `true`, the result is `VALID`
- when it returns `false`, the result is `INVALID`

The current implementation reports only the first matching step for each requirement type.

## Result Contract

### Status

- `VALID`
- `INVALID`

### Error

```json
{
  "code": "SKILL_SERVER_UNAVAILABLE",
  "message": "SKILL_SERVER_UNAVAILABLE: skill requires local server for wait_channel (step=listen_whatsapp)"
}
```

For `wait_webhook`, the same code is used and the message changes the step type:

```text
SKILL_SERVER_UNAVAILABLE: skill requires local server for wait_webhook (step=listen_webhook)
```

For WhatsApp channel availability:

```json
{
  "code": "SKILL_WHATSAPP_UNAVAILABLE",
  "message": "SKILL_WHATSAPP_UNAVAILABLE: skill requires active WhatsApp bridge for send (step=reply)"
}
```

## Boundary

`SkillServerCheckerUseCase` does:
- load the skill
- inspect `steps`
- check whether the server is available
- check whether a required channel bridge is available

`SkillServerCheckerUseCase` does not:
- validate general skill structure
- start the server
- start the channel bridge
- create a run
- append runtime events
