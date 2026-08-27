# `skiller webhook`

Receives webhook payloads and manages webhook registrations.

## Combinations

| Command | Behavior | Returns |
| --- | --- | --- |
| `skiller webhook receive <webhook> <key> --json '{"ok": true}'` | Delivers an inline JSON payload to matching waits. | Delivery result and resumed run ids. |
| `skiller webhook receive <webhook> <key> --json-file payload.json` | Delivers a JSON payload from a file. | Delivery result and resumed run ids. |
| `skiller webhook receive <webhook> <key> --json '{"ok": true}' --dedup-key <key>` | Delivers an idempotent webhook payload. | Delivery result and resumed run ids. |
| `skiller webhook register <webhook>` | Registers a local webhook channel and secret. | Registration details. |
| `skiller webhook register <webhook> --method GET --auth none --payload-source query` | Registers a query-string webhook. | Registration details. |
| `skiller webhook register <webhook> --auth token --token-header X-Webhook-Token` | Registers a fixed-token webhook. | Registration details. |
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

Options:

- `--method`: accepted HTTP method. Supported values: `POST`, `GET`.
- `--auth`: endpoint authentication mode. Supported values: `signed`, `token`, `none`.
- `--token-header`: required with `--auth token`; the request header carrying the fixed token. It is invalid with other authentication modes.
- `--payload-source`: where the endpoint reads the payload. Supported values: `body_json`, `query`.

Valid method and payload-source pairs:

- `POST` with `body_json`
- `GET` with `query`

Output:

```json
{
  "webhook": "github-ci",
  "status": "REGISTERED",
  "method": "POST",
  "auth": "signed",
  "payload_source": "body_json",
  "secret": "secret-value",
  "enabled": true,
  "webhook_url": "http://127.0.0.1:8001/webhooks/github-ci/{key}"
}
```

Query-string webhook:

```bash
skiller webhook register oauth-callback --method GET --auth none --payload-source query
```

Invalid method and payload-source combinations return `INVALID_CONFIG`.

### Header token webhook

Use `token` when a provider sends a fixed shared secret in a request header:

```bash
skiller webhook register provider-events \
  --auth token \
  --token-header X-Webhook-Token
```

The registration response contains the generated `secret` and `token_header`. Configure the
provider to send that secret as the exact value of the configured header. Skiller compares the
value in constant time. Do not store the secret in flow files or source control.

`token_header` is required only for `--auth token`. The server returns `401` when the header is
missing or its value does not match.

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
    "method": "POST",
    "auth": "signed",
    "payload_source": "body_json",
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
- `1`: the payload was invalid, resume dispatch failed, registration failed, or removal failed.
