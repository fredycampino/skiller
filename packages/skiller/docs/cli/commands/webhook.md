# `skiller webhook`

Receives webhook payloads and manages webhook registrations.

## Combinations

| Command | Behavior | Returns |
| --- | --- | --- |
| `skiller webhook receive <webhook> <key> --json '{"ok": true}'` | Delivers an inline JSON payload to matching waits. | Delivery result and resumed run ids. |
| `skiller webhook receive <webhook> <key> --json-file payload.json` | Delivers a JSON payload from a file. | Delivery result and resumed run ids. |
| `skiller webhook receive <webhook> <key> --json '{"ok": true}' --dedup-key <key>` | Delivers an idempotent webhook payload. | Delivery result and resumed run ids. |
| `skiller webhook register <webhook>` | Registers a local webhook channel and secret. | Registration details. |
| `skiller webhook list` | Lists local webhook registrations. | JSON array of registrations. |
| `skiller webhook remove <webhook>` | Removes a local webhook registration. | Removal result. |

## Receive Output Model

- `accepted`: whether the webhook payload was accepted.
- `duplicate`: whether the payload was ignored as a duplicate delivery.
- `webhook`: webhook channel name.
- `key`: webhook correlation key.
- `matched_runs`: runs matched by the webhook event.
- `resumed_runs`: matched runs for which a worker resume was dispatched.

## Receive Inline JSON

Command:

```bash
skiller webhook receive github-ci build-42 --json '{"status": "ok"}'
```

Output:

```json
{
  "accepted": true,
  "duplicate": false,
  "webhook": "github-ci",
  "key": "build-42",
  "matched_runs": ["run-uuid"],
  "resumed_runs": ["run-uuid"]
}
```

## Receive JSON File

Command:

```bash
skiller webhook receive github-ci build-42 --json-file payload.json
```

The file must contain a JSON object.

## Deduplication

Command:

```bash
skiller webhook receive github-ci build-42 --json '{"status": "ok"}' --dedup-key delivery-42
```

`--dedup-key` makes repeated deliveries idempotent for the same webhook event.

## Register

Command:

```bash
skiller webhook register github-ci
```

Output:

```json
{
  "webhook": "github-ci",
  "status": "REGISTERED",
  "secret": "secret-value",
  "enabled": true,
  "webhook_url": "http://127.0.0.1:8001/webhooks/github-ci/{key}"
}
```

## List

Command:

```bash
skiller webhook list
```

Output:

```json
[
  {
    "webhook": "github-ci",
    "secret": "secret-value",
    "enabled": true,
    "created_at": "2026-05-12 10:30:15"
  }
]
```

## Remove

Command:

```bash
skiller webhook remove github-ci
```

Output:

```json
{
  "webhook": "github-ci",
  "status": "REMOVED",
  "removed": true
}
```

## Exit Code

- `0`: the command completed successfully.
- `1`: the payload was invalid, the delivery was rejected, resume dispatch failed, registration failed, or removal failed.
