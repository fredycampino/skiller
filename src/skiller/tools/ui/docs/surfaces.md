# UI Surfaces

This document describes the basic visible surfaces of the current UI.
It focuses on what each surface is responsible for and what the user can expect to see there.

## Title

Purpose:
Display the product identity and the current session key.

Behavior:
The title surface stays visible at the top of the UI and does not accept user input.

Inputs:
Current session key.

Visible Output:
The `Skiller` label and the active session identifier.

Rules:
The title surface is informational only.

## Meta

Purpose:
Display the current console context for the active session.

Behavior:
The meta surface stays visible below the title and reflects the currently selected run when available.

Inputs:
Current selected run id.

Visible Output:
The console label and the selected run reference.

Rules:
If no run is selected, the surface shows an empty or placeholder selected state.

## Output

Purpose:
Display the main UI transcript and command results.

Behavior:
The output surface accumulates rendered results such as help text, run status, logs, session details, and command feedback.

Inputs:
Rendered command results and system messages.

Visible Output:
Scrollable text content representing the current UI transcript.

Rules:
The output surface is read-only from the user's point of view.
It can be cleared by a clear action.

## Status Bar

Purpose:
Display the current execution state of the UI.

Behavior:
The status bar reflects whether the UI is idle, processing a command, waiting on a run, or showing a completed result state.

Inputs:
Current command state and the latest action result.

Visible Output:
A single-line status message.
When the UI is busy, the line may include a spinner.

Rules:
The status bar summarizes state only.
It does not display full command output.

## Command Input

Purpose:
Capture text entered by the user.

Behavior:
The command input accepts slash commands and free text.
It is the primary interactive entry point of the UI.

Inputs:
Keyboard input from the user.

Visible Output:
The current editable input buffer and prompt marker.

Rules:
Slash-prefixed input is interpreted as a command.
Submission behavior depends on the current input content.
The command input may open the autocomplete menu.

## Footer

Purpose:
Display lightweight usage hints and recent run context.

Behavior:
The footer stays visible at the bottom of the UI and provides short operational guidance.

Inputs:
Last known run id and static shortcut hints.

Visible Output:
The latest run reference and shortcut guidance.

Rules:
The footer is informational only.

## Autocomplete Menu

Purpose:
Suggest matching slash commands while the user types a command prefix.

Behavior:
The autocomplete menu appears near the input area when command suggestions are available.

Inputs:
The current slash-command prefix under the cursor.

Visible Output:
A floating list of matching command names.

Rules:
Only command names are suggested.
Command arguments are not suggested.
The menu is part of command entry, not a general search surface.
