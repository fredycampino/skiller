# `notify`

## Goal

`notify` emits a message into the transcript and stores that message as the step output.

## Shape

```yaml
- notify: show_reply
  message: '{{output_value("answer").data.reply}}'
  next: ask_user
```

## Persistence

```json
{
  "output": {
    "text": "hello back",
    "value": {
      "message": "hello back"
    },
    "body_ref": null
  }
}
```

If `next` is missing, the run completes after the step.
