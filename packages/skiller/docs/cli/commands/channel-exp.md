# `skiller channel`

Receives generic channel payloads into the runtime.

This command is experimental. It is available for externally managed channel
integrations, but the public contract may still change.

## Command

| Command | Behavior | Returns |
| --- | --- | --- |
| `skiller channel receive <channel> <key> --json '{"text": "hi"}'` | Delivers an inline JSON payload to matching waits. | Delivery result and resumed run ids. |
| `skiller channel receive <channel> <key> --json-file payload.json` | Delivers a JSON payload from a file. | Delivery result and resumed run ids. |
| `skiller channel receive <channel> <key> --json '{"text": "hi"}' --external-id msg-1` | Delivers a payload with provider message id. | Delivery result and resumed run ids. |
| `skiller channel receive <channel> <key> --json '{"text": "hi"}' --dedup-key msg-1` | Delivers an idempotent payload. | Delivery result and resumed run ids. |

## Output Model

- `accepted`: whether the channel payload was accepted.
- `duplicate`: whether the payload was ignored as a duplicate delivery.
- `channel`: channel name.
- `key`: channel correlation key.
- `external_id`: external message id, present when provided.
- `matched_runs`: runs matched by the channel event.
- `resumed_runs`: matched runs for which a worker resume was dispatched.
- `error`: failure reason, present when the payload was rejected.

## Receive Inline JSON

Command:

```bash
skiller channel receive whatsapp contact-1 --json '{"text": "hello"}'
```

Output:

```json
{
  "accepted": true,
  "duplicate": false,
  "channel": "whatsapp",
  "key": "contact-1",
  "matched_runs": ["run-uuid"],
  "resumed_runs": ["run-uuid"]
}
```

## Receive JSON File

Command:

```bash
skiller channel receive whatsapp contact-1 --json-file payload.json
```

The file must contain a JSON object.

## Deduplication

Command:

```bash
skiller channel receive whatsapp contact-1 --json '{"text": "hello"}' --dedup-key msg-1
```

`--dedup-key` makes repeated deliveries idempotent for the same channel event.

## Exit Code

- `0`: the payload was accepted and any matched runs were dispatched for resume.
- `1`: the payload was rejected or a worker resume could not be started.
