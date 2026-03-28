# Waiting Input State

### Trigger
A run enters a `wait_input` step.

### Status Bar
Shows the waiting-input state and the rendered prompt for the selected run.

### Command Input
Accepts a free-text reply for the selected waiting run.

### Submit
Pressing `Enter` sends the reply to the runtime.

### Preconditions
A run must be selected.
The selected run must be in `wait_input`.

### Validation
Empty replies must not be submitted.

### Error Handling
If the runtime rejects the reply, the UI must show the error in the output area and update the status bar.

### Result
After submission, the UI refreshes the run state.
