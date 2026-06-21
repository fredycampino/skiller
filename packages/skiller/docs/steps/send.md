# `send`

## Goal

`send` sends a text message through a configured channel sender and stores the accepted delivery metadata as step output.

The default runtime does not configure a channel sender, so `send` is currently disconnected unless a runtime build injects one.

## Shape

```yaml
- send: reply_channel
  channel: external
  key: '{{output_value("listen_channel").key}}'
  message: 'Received: {{output_value("listen_channel").payload.text}}'
  next: done
```

Rules:
- `channel` identifies the configured sender channel
- `key` is the target channel key
- `message` is plain text
- without an injected sender, execution fails with `Channel sending is not configured`

## Persistence

```json
{
  "output": {
    "text": "Message sent: external:contact-1.",
    "value": {
      "channel": "external",
      "key": "contact-1",
      "message": "Received: hello",
      "message_id": "msg-123"
    },
    "body_ref": null
  }
}
```

If `next` is missing, the run completes after the step.
