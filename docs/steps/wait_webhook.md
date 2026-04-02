# `wait_webhook`

## Goal

`wait_webhook` pauses a run until an external event arrives for the expected `webhook + key`.

## Shape

```yaml
- wait_webhook: wait_merge
  webhook: github-pr-merged
  key: '{{output_value("create_pr").data.pr}}'
  next: done
```

## Waiting Output

```json
{
  "output": {
    "text": "Waiting webhook: github-pr-merged:42.",
    "value": {
      "webhook": "github-pr-merged",
      "key": "42",
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
    "text": "Webhook received: github-pr-merged:42.",
    "value": {
      "webhook": "github-pr-merged",
      "key": "42",
      "payload": {
        "merged": true
      }
    },
    "body_ref": null
  }
}
```

Template access:

```text
{{output_value("wait_merge").payload.merged}}
```
