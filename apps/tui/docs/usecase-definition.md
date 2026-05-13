# TUI Use Case Definition

## Purpose

This document defines what a `use case` is in the TUI and how it should look and behave.

It is the design contract for application behavior in `apps/tui/src/stui/usecase`.

## Definition

A TUI `use case` is a small application unit that:

- receives a UI intent or a normalized runtime event
- applies presentation and flow rules
- uses `port` dependencies when external data or runtime actions are needed
- returns updated state or explicit result data to the `viewmodel`

A use case is not a widget, not an adapter, and not a general service layer.

## Role In The Architecture

The TUI architecture is state-driven.

The screen renders `ConsoleScreenState`.
The viewmodel decides which use case to call.
The use case performs one focused interaction or transformation.

Target flow:

```text
Screen
-> ViewModel
-> UseCase
-> Port
-> Adapter
-> runtime / CLI
-> ViewModel emits state
-> Screen re-renders
```

## What A Use Case Owns

A use case should own one of these:

- one user interaction
- one state transition
- one state projection
- one event reduction step

Examples:

- dispatch a `/run`
- list `/runs`
- apply autocomplete selection
- project transcript items for chat mode
- reduce normalized runtime events into presentation state

## What A Use Case Must Not Own

A use case must not:

- talk to Textual widgets directly
- render Rich or Textual output
- create infrastructure objects
- call subprocess or CLI code directly
- spread one feature across unrelated state transitions without a clear boundary

## Structure

A use case should usually have:

- one file
- one class
- one `execute(...)` entry point
- explicit typed inputs
- explicit typed outputs when needed

Preferred shape:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class SomeResult:
    state: ConsoleScreenState
    did_change: bool


@dataclass(frozen=True)
class SomeUseCase:
    some_port: SomePort

    async def execute(
        self,
        *,
        state: ConsoleScreenState,
        input: SomeInput,
    ) -> SomeResult:
        ...
```

## Behavior Rules

### `Focused`

A use case should resolve one interaction or transformation only.

If a class is doing dispatch, session activation, transcript rewriting, prompt resetting, and observer wiring at once, it is too large.

### `State-based`

A use case should operate on state models, not on widgets.

All UI consequences should be expressed through `ConsoleScreenState` or explicit result values.

### `Port-driven I/O`

If a use case needs runtime data or needs to send commands, it should do so through `port` dependencies only.

It should not know subprocess details or CLI argument assembly.

### `Blocking I/O Offloading`

If a port call is blocking, the use case should offload it with `asyncio.to_thread(...)`.

The UI loop must stay responsive.

### `Deterministic`

Given:

- input
- current state
- current context
- port response

the output should be predictable and testable.

### `Directly Testable`

A use case should be testable without:

- a running Textual app
- real subprocesses
- real adapters

Tests should be able to provide fake ports and inspect resulting state.

## Boundaries

### `Screen`

- captures keyboard and mouse input
- manages widget lifecycle
- renders `ConsoleScreenState`

### `ViewModel`

- decides which use case to call
- sequences interactions
- emits the updated state

### `UseCase`

- owns the transition logic
- updates state
- coordinates ports for one focused behavior

### `Adapter`

- talks to CLI or runtime
- parses external payloads
- hides transport details from use cases

## Use Case Types In This UI

The TUI currently benefits from these categories:

### `Interaction use case`

Handles a user action.

Examples:

- run command
- list runs
- submit waiting input

### `Projection use case`

Projects state into a view-specific form.

Examples:

- transcript projection for chat mode

### `Reducer use case`

Reduces normalized events into presentation state.

Examples:

- log event reducer

### `Selection use case`

Changes the active session or selection context.

Examples:

- selecting a run from the runs table

## Quality Checklist

A TUI use case is healthy when it is:

- small
- explicit
- typed
- cohesive
- easy to test
- independent from Textual widgets
- isolated from CLI details

A TUI use case needs refactor when it shows these signs:

- too many responsibilities
- heavy branching on unrelated concerns
- direct coupling to rendering concerns
- hidden synchronous blocking calls
- duplicated state mutation rules
- transcript semantics mixed with transport semantics and session orchestration

## Practical Rule

If a use case must be explained as:

- "it mostly does one thing, but also resets prompt, changes transcript mode, loads session, subscribes observer, and handles runtime edge cases"

then it is no longer a clean use case boundary.

It should be split.

## Short Definition

A good TUI use case is a small, explicit, testable unit that owns one application behavior, expresses UI effects through state, and reaches external systems only through ports.
