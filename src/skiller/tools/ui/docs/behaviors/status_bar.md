# Status Bar

### Idle
When no command is running and no new result is being processed, the status bar shows:

`· Idle`

### Loading
When the UI is processing a non-run command, the status bar shows:

`◐ Loading [action]`

### Progress
When the UI is processing an in-progress state, the status bar shows an animated `progress` marker before the status text.

Example:

`◐ Loading logs`

### Running Run
When a run is in progress, the status bar shows:

`◐ Running [run-label]`

### Waiting Input
When a run enters `wait_input`, the status bar shows:

`◌ Waiting → [prompt]`

### Waiting Webhook
When a run enters `wait_webhook`, the status bar shows:

`◌ Waiting [webhook]`

### Success
When a run completes successfully, the status bar shows:

`✓ Success [run-label]`

### Error
When a run fails, the status bar shows:

`× Error`

### Non-Run Results
When a non-run command completes, the status bar shows a short result label.

Examples:

`Ready`
`Cleared`
`Loaded 2 runs`
`Loaded 1 webhook`
`Loaded logs [run-id]`
`Input sent [run-id]`
`Closing`

### Busy State
When the UI is busy, the status bar may display the current status text together with `progress`.
