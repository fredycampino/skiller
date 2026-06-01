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
    message: "Continue authorization in the browser."
    url: "https://example.com/oauth/start"
    auto: true
```

Supported action types:

- `open_url`: opens an HTTP(S) URL.

`action.label` and `action.url` are required. `action.url` must start with
`http://` or `https://`. `action.auto` is optional and defaults to `false`.

`action.message` is optional. Runtime resolves the action message as follows:

- when `action.message` is present and non-empty, that value is used;
- when `action.message` is omitted, null, or empty, runtime uses the resolved
  notify step `message`.

Example without `action.message`:

```yaml
- notify: auth_link
  message: '{{output_value("wait_any_text").payload.text}}'
  action:
    type: open_url
    label: "Open authorization"
    url: "https://example.com/oauth/start"
```

If the notify message resolves to `Authorize the app`, the stored action will
include:

```json
{
  "action": {
    "type": "open_url",
    "label": "Open authorization",
    "message": "Authorize the app",
    "url": "https://example.com/oauth/start",
    "auto": false
  }
}
```

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
      "action": {
        "type": "open_url",
        "label": "Open authorization",
        "message": "Continue authorization in the browser.",
        "url": "https://example.com/oauth/start",
        "auto": true
      }
    },
    "body_ref": null
  }
}
```

The notify output stores the declared action. Mutable action state is not stored
in the run context; a completed action is represented by an `ACTION_DONE`
runtime event.

Mark an action as done:

```bash
skiller action done <run_id> <step_id>
```

If `next` is missing, the run completes after the step.
