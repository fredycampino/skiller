# `skiller server`

Manages the local webhook server and writes JSON to `stdout`.

The server hosts:

- external webhook ingress: `POST /webhooks/{webhook}/{key}`
- local channel ingress: `POST /channels/{channel}/{key}`

## Combinations

| Command | Behavior | Returns |
| --- | --- | --- |
| `skiller server start` | Starts the local webhook server if needed. | Server process state. |
| `skiller server status` | Reads local webhook server state. | Server process state. |
| `skiller server stop` | Stops the managed local webhook server process. | Stop result and process state. |

## Output Model

Common fields:

- `running`: whether the server endpoint responds.
- `managed_by_skiller`: whether Skiller owns the local server process.
- `endpoint`: health endpoint for the local server.
- `pid`: local process id when known.

`start` also returns:

- `started`: whether this command started a new managed process.

`stop` also returns:

- `stopped`: whether a managed process was stopped.

## Start

Command:

```bash
skiller server start
```

Output:

```json
{
  "started": true,
  "running": true,
  "managed_by_skiller": true,
  "endpoint": "http://127.0.0.1:8001/health",
  "pid": 12345
}
```

## Status

Command:

```bash
skiller server status
```

Output:

```json
{
  "running": true,
  "managed_by_skiller": true,
  "endpoint": "http://127.0.0.1:8001/health",
  "pid": 12345
}
```

## Stop

Command:

```bash
skiller server stop
```

Output:

```json
{
  "stopped": true,
  "running": false,
  "managed_by_skiller": true,
  "endpoint": "http://127.0.0.1:8001/health",
  "pid": 12345
}
```

`stop` only stops a process managed by Skiller.

## State

Managed process state lives under `~/.skiller/webhooks/managed-<port>.json`.
If `SKILLER_DEBUG_HOME` is set, that directory becomes the effective `HOME`.

## Exit Code

- `0`: the command completed successfully.
- `1`: start or stop failed, or `stop` could not stop a running server.
