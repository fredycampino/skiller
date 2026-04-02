# `skiller server`

Manage the local webhooks server.

## Commands

```bash
skiller server start
skiller server status
skiller server stop
```

## State

- Managed state lives under `~/.skiller/webhooks/managed-<port>.json`.
- If `SKILLER_DEBUG_HOME` is set, that directory becomes the effective `HOME`.

## Output

Key fields:
- `running`
- `managed_by_skiller`
- `endpoint`
- `pid`

Example:

```json
{
  "running": true,
  "managed_by_skiller": false,
  "endpoint": "http://127.0.0.1:8001/health",
  "pid": null
}
```

Meaning:
- `running: true` means the endpoint responds.
- `managed_by_skiller: true` means Skiller owns the local process.
- `stop` only stops a process owned by Skiller.
