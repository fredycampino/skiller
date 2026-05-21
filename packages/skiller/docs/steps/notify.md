# `notify`

## Goal

`notify` emits a message into the transcript and stores that message as the step output.

## Shape

```yaml
- notify: show_reply
  message: '{{output_value("answer").data.reply}}'
  format: markdown
  next: ask_user
```

`format` is optional. Supported values are `simple`, `structured`, and `markdown`.
When omitted, `simple` is used.

## Persistence

```json
{
  "output": {
    "text": "hello back",
    "value": {
      "message": "hello back",
      "format": "simple"
    },
    "body_ref": null
  }
}
```

If `next` is missing, the run completes after the step.
