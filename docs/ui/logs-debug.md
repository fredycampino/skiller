# Logs Debug

### Goal
Define `/logs` as a raw debug surface, not as part of the user-facing run transcript.

### Scope
This behavior applies to:
- explicit `/logs`
- the `logs` action result in the TUI

It does not define:
- `/run`
- `/watch`
- the run transcript shown for normal execution flow

### Contract
`/logs` shows the raw structured event stream for a run.

It is intended for:
- debugging
- inspecting exact event order
- checking runtime payloads
- understanding failures at event level

It is not intended for:
- polished user-facing execution flow
- hiding technical detail
- replacing the run transcript

### Rendering
`/logs` keeps a simple raw/debug rendering.

### Relationship To Transcript
The transcript and `/logs` have different responsibilities:

- transcript:
  - user-facing execution view
  - renders selected runtime events as readable steps

- `/logs`:
  - raw/debug event stream
  - exposes exact event payloads

### Relationship To `watch`
`watch` may still print compact progress lines to `stderr` for direct CLI usage.

That compact `stderr` stream is:
- useful for humans running `skiller watch <run_id>` directly
- not part of the TUI transcript contract
- not a source of truth for UI rendering

The UI transcript should consume structured `events`, not `stderr` text.
