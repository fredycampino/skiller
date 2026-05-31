# TUI Status View Spec

## Goal

Define how the global TUI status should look.

This is the visual spec for the global status component only.

It does not define:
- run-local status inside the transcript
- polling internals
- transcript formatting

## Scope

The status view is a single global visual component.

It shows:
- the current global state of the TUI

It does not show:
- run-local `created`
- run-local `succeeded`
- run-local `waiting`
- run-local runtime error details

Those belong to the run session block in the transcript.

## Component Role

The global status is rendered by `ScreenStatusView`.

The input state is `ScreenStatus`.

Current modeled states:
- `HIDDEN`
- `RUNNING`
- `WAITING`
- `ERROR`

## Visual Rules

- Do not prefix with `status:`
- Use short, stable labels
- Only `RUNNING` animates
- The component should stay visually small and secondary

## State Mapping

### `HIDDEN`

Target shape:

```text

```

Rules:
- no animation
- renders no visible text

### `RUNNING`

Target shape:

```text
◐ Running
◓ Running
◑ Running
◒ Running
```

Rules:
- use the current circular spinner frames from the theme
- animate locally in the status view
- keep the label stable as `Running`

### `WAITING`

Target shape:

```text
... [Write a message. Type exit, quit, or bye to stop.]
```

Rules:
- no animation
- neutral/default text color
- include the current waiting prompt in brackets
- the bracketed prompt uses muted style
- this prompt is global status content; it must not be duplicated in transcript output

### `ERROR`

Target shape:

```text
Error
```

Rules:
- no animation
- use the theme error color

## Semantics

- `HIDDEN`
  - the TUI has no global status to show

- `RUNNING`
  - a command is being dispatched or a run is actively progressing

- `WAITING`
  - the active run is waiting for input or another external signal

- `ERROR`
  - the latest global outcome is an error

## Ownership

### `ConsoleScreenViewModel`
- decides the current `ScreenStatus`

### `ScreenStatusView`
- renders that status
- owns the running animation timer

## Example

```text

◐ Running
...
Error
```
