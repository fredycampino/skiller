# `wait_channel`

## Goal

`wait_channel` pauses a run until a channel message arrives for the expected channel scope.

Runtime correlation:
- `source_type = channel`
- `source_name = <channel>`
- `match_type = channel_key`
- `match_key = <key>` or `all`

Current semantics:
- events created before the run are ignored
- events created during the run may resolve the wait, even if they arrived before the step was reached
- each external event is single-consumer
- if multiple pending channel messages could match, the oldest one is consumed first

## Shape

External systems can deliver channel events through the generic channel ingress.

```yaml
- wait_channel: listen_channel
  channel: external
  key: all
  next: notify_message
```

## Waiting Output

```json
{
  "output": {
    "text": "Waiting channel: external:all.",
    "value": {
      "channel": "external",
      "key": "all",
      "payload": null
    },
    "body_ref": null
  }
}
```

## Resolved Output

```json
{
  "output": {
    "text": "Channel message received: external:contact-1.",
    "value": {
      "channel": "external",
      "key": "contact-1",
      "payload": {
        "message_id": "msg-1",
        "key": "contact-1",
        "sender_id": "contact-1",
        "sender_name": "Sender",
        "text": "hello",
        "timestamp": 1775388655
      }
    },
    "body_ref": null
  }
}
```

Template access:

```text
{{output_value("listen_channel").payload.text}}
{{output_value("listen_channel").key}}
```
