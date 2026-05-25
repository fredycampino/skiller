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

`format` is optional. Supported values are `simple`, `structured`, and
`markdown`.
When omitted, `simple` is used.

## Action

Add `action` when the transcript must expose a user action. `format` still only
controls message rendering.

```yaml
- notify: auth_link
  format: markdown
  message: "Authorize the app"
  action:
    type: open_url
    label: "Open authorization"
    url: "https://example.com/oauth/start"
    auto_open: true
```

Supported action types:

- `open_url`: opens an HTTP(S) URL.

`action.label` and `action.url` are required. `action.url` must start with
`http://` or `https://`. `action.auto_open` is optional and defaults to `false`.

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

For notify actions, runtime stores a typed action:

```json
{
  "output": {
    "text": "Authorize the app",
    "value": {
      "message": "Authorize the app",
      "format": "markdown",
      "action_type": "open_url",
      "action": {
        "label": "Open authorization",
        "url": "https://example.com/oauth/start",
        "status": "pending",
        "auto_open": true
      }
    },
    "body_ref": null
  }
}
```

Action status values:

- `pending`: action is available to the user.
- `done`: action was executed by the UI/client.

Mark an action as done:

```bash
skiller action done <run_id> <step_id>
```

If `next` is missing, the run completes after the step.
