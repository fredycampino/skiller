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

```yaml
- wait_channel: listen_whatsapp
  channel: whatsapp
  key: all
  next: notify_message
```

## Waiting Output

```json
{
  "output": {
    "text": "Waiting channel: whatsapp:all.",
    "value": {
      "channel": "whatsapp",
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
    "text": "Channel message received: whatsapp:172584771580071@lid.",
    "value": {
      "channel": "whatsapp",
      "key": "172584771580071@lid",
      "payload": {
        "channel": "whatsapp",
        "message_id": "msg-1",
        "key": "172584771580071@lid",
        "sender_id": "172584771580071@lid",
        "sender_name": "Fede",
        "text": "hola",
        "timestamp": 1775388655
      }
    },
    "body_ref": null
  }
}
```

Template access:

```text
{{output_value("listen_whatsapp").payload.text}}
{{output_value("listen_whatsapp").key}}
```
