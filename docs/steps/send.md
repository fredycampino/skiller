# `send`

## Goal

`send` sends a text message through a channel adapter and stores the accepted delivery metadata as step output.

## Shape

```yaml
- send: reply_whatsapp
  channel: whatsapp
  key: '{{output_value("listen_whatsapp").key}}'
  message: 'Hola: {{output_value("listen_whatsapp").payload.text}}'
  next: done
```

v1 rules:
- `channel` must be `whatsapp`
- `key` is the target channel key
- `message` is plain text

## Persistence

```json
{
  "output": {
    "text": "Message sent: whatsapp:172584771580071@lid.",
    "value": {
      "channel": "whatsapp",
      "key": "172584771580071@lid",
      "message": "Hola",
      "message_id": "wamid-123"
    },
    "body_ref": null
  }
}
```

If `next` is missing, the run completes after the step.
