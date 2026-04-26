# `skiller whatsapp`

Manage the local WhatsApp channel bridge and pairing lifecycle.

## Commands

```bash
skiller whatsapp pair start
skiller whatsapp pair status
skiller whatsapp pair stop

skiller whatsapp start
skiller whatsapp status
skiller whatsapp stop
```

## Pairing

`pair start` uses the bridge in `--pair-only` mode and persists the session under:

```text
~/.skiller/whatsapp/session
```

Exact behavior:
- if `~/.skiller/whatsapp/session/creds.json` already exists, `pair start` returns `paired: true` and does not start a new pairing process
- if a managed pairing process is already running, `pair start` returns its current state and does not start another one
- otherwise `pair start` launches the Node bridge in foreground with `--pair-only`, streams its output, and waits for it to exit
- pairing uses a 120 second timeout

`pair` is still the manual prerequisite. A paired session is required before `start`.

## Runtime Model

`whatsapp start` now means the channel is active end-to-end:
- ensures the local `skiller server` is running
- starts or reuses the local Node bridge
- configures local signal push from the bridge into the local channel ingress on the shared server
- resumes matching `wait_channel` runs automatically

There is no public `poll` command.

Bridge delivery uses:

```text
POST /channels/whatsapp/{key}
```

For the current WhatsApp channel flow:
- `key = WhatsApp chat id`

Outbound sends wait for the bridge response so the runtime can store the WhatsApp `message_id`.
The bridge intentionally simulates human typing before sending, with a delay up to 6.5 seconds by
default. Skiller waits up to `AGENT_WHATSAPP_BRIDGE_SEND_TIMEOUT_SECONDS` seconds for that response;
the default is 10 seconds.

## State

Managed state lives under:

```text
~/.skiller/whatsapp/
```

Important files:
- `pair.json`: managed pairing process ownership
- `pair-runtime.json`: pairing runtime state written by the Node process
- `pair.log`: pairing output log
- `managed-<bridge-port>.json`: managed bridge ownership
- `channel-token-<bridge-port>.txt`: local channel ingress token shared with the server
- `session/`: persisted WhatsApp auth state
- `bridge-runtime.json`: bridge-side runtime state written by the Node process

If `SKILLER_DEBUG_HOME` is set, that directory becomes the effective `HOME`.

## Pair Output

`whatsapp pair start` returns:
- `paired`
- `started`
- `running`
- `pid`
- `state`
- `qr_count`
- `home`
- `session_path`
- `log_path`

`whatsapp pair status` returns:
- `paired`
- `running`
- `pid`
- `state`
- `qr_count`
- `home`
- `session_path`
- `log_path`

`whatsapp pair stop` returns:
- `paired`
- `stopped`
- `running`
- `pid`
- `state`
- `qr_count`
- `home`
- `session_path`
- `log_path`

Pairing state rules:
- if a session is already paired, `state = paired`
- if a managed pairing process is running and `pair-runtime.json` contains a non-empty `state`, that value is returned
- if a managed pairing process is running and `pair-runtime.json` does not contain `state`, `state = waiting_for_scan`
- if no session is paired and no managed pairing process is running, `state = stopped`

## Channel Output

Key fields:
- `running`
- `managed_by_skiller`
- `paired`
- `state`
- `qr_count`
- `queue_length`
- `endpoint`
- `pid`

Example:

```json
{
  "running": true,
  "managed_by_skiller": true,
  "paired": true,
  "state": "connected",
  "qr_count": 0,
  "queue_length": 0,
  "endpoint": "http://127.0.0.1:8002/health",
  "session_path": "/home/fede/.skiller/whatsapp/session",
  "pid": 45592
}
```

Meaning:
- `running: true` means the bridge health endpoint responds and the shared local server is available.
- `managed_by_skiller: true` means Skiller owns the local bridge process.
- `paired: true` means a saved WhatsApp session exists.
- `state` reflects the bridge connection state.
- `queue_length` is the current bridge-side fallback queue length.
- `stop` only stops a process owned by Skiller.

## Typical Flow

1. Pair once:

```bash
skiller whatsapp pair start
```

2. Start the channel:

```bash
skiller whatsapp start
```

3. Run a skill that waits on WhatsApp:

```bash
skiller run whatsapp_demo
```

4. Inspect channel state if needed:

```bash
skiller whatsapp status
```
