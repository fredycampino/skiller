# TUI Architecture

## Purpose

This document explains the architectural patterns used by the TUI. It does not document command syntax or command semantics. Those live in [`../../instructions/skiller-user.md`](../../instructions/skiller-user.md).

## Core Patterns

### `State-driven UI`
- `ConsoleScreenState` is the source of truth for screen-visible behavior
- `ConsoleScreen` distributes each state section to its View through `set_state(...)`
- the UI does not render raw runtime payloads directly
- transcript, prompt, autocomplete, status, session, tables, actions, and metrics are presentation state
- rendering is a projection of state, not a direct reaction to raw transport payloads
- a View may retain an immutable snapshot of its last applied representation to avoid redundant rendering
- View snapshots are render caches, not business state or an alternative source of truth

### `ViewModel as Orchestrator`
- the screen emits user intent
- the viewmodel decides which use case to call
- the viewmodel emits the updated state back to the screen
- the viewmodel coordinates behavior, but it does not own runtime transport details

### `Use Case per Interaction`
- each interaction is handled by a focused use case
- use cases expose `execute(...)`
- use cases receive dependencies through `port` or `context`
- use cases return state or result data to the viewmodel
- use cases own behavior, not widgets

### `Ports and Adapters Boundary`
- ports define what the TUI needs from the outside world
- adapters implement those contracts against the CLI/runtime
- the viewmodel and screen do not talk to subprocess or polling code directly
- transport, parsing, and subscription details stay below the use case layer

### `Event Reduction`
- external runtime events are first normalized
- normalized events are then reduced into presentation state
- transcript items, waiting state, and status changes are derived from normalized events
- the reducer layer owns event-to-state rules

### `Blocking I/O Offloading`
- blocking runtime calls use `asyncio.to_thread(...)`
- the async UI loop stays responsive while the CLI is queried
- synchronous infrastructure must not leak into direct UI interaction paths

## State Model

`ConsoleScreenState` is the central UI contract.

It holds presentation state for the transcript, prompt, autocomplete, status, session, tables, actions, and agent metrics.

This allows the screen to render from state instead of from runtime responses. `ConsoleScreen` coordinates the Views, while each View owns how and when its state section is applied to Textual widgets.

The important architectural rule is not the exact field list. Screen-visible behavior must be represented as explicit state, not as hidden widget-local logic.

A View may additionally own ephemeral visual state such as focus, selection, animation position, responsive layout, or its last rendered snapshot. This local state must not redefine application behavior and must remain derivable from the presentation state plus widget lifecycle.

## Layer Responsibilities

### `Screen`
- composes Views and owns screen-level Textual lifecycle
- captures keyboard input and coordinates cross-View focus and layout
- forwards intent to the viewmodel
- distributes sections of `ConsoleScreenState` to Views

### `View`
- owns its Textual widgets and local visual lifecycle
- receives explicit presentation state through `set_state(...)`
- decides how to render its state section
- avoids redundant widget updates when the applied representation has not changed
- owns local invalidation caused by resize, animation, focus, or selection

### `ViewModel`
- orchestrates presentation behavior
- coordinates dispatch, query, waiting input, autocomplete, and observation
- updates and emits `ConsoleScreenState`
- does not perform transport work directly

### `UseCase`
- owns one interaction or transformation
- applies presentation rules outside the screen
- stays small and directly testable
- expresses UI effects through state or explicit result models

### `Port`
- defines external capabilities needed by the TUI
- isolates the TUI from concrete runtime transport

### `Adapter`
- implements ports using the CLI/runtime
- translates external payloads into TUI-friendly data
- keeps subprocess, polling, and mapping details out of higher layers

## Interaction Patterns

### `Dispatch pattern`

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

### `Query pattern`

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

### `Observation pattern`

```text
Runtime event source
-> event observer
-> event mapper
-> event reducer use case
-> ViewModel emits state
-> Screen re-renders
```

Rules:

- event observation is asynchronous
- raw external events are mapped before they reach the reducer
- reducers operate on normalized events, not transport payloads

### `Prompt assistance pattern`

```text
Prompt change
-> ViewModel
-> AutocompleteUseCase
-> ViewModel emits state
-> Screen re-renders
```

### `Overlay pattern`

```text
Use case or screen action
-> updates overlay-related state
-> screen shows or hides the overlay
```

## Stability Rule

This document describes architectural patterns, not a catalog of concrete classes.

If a class, adapter, or reducer changes name, this document should remain valid.

If a pattern changes, this document must be updated.

## Design Rules

- screens do not make business decisions
- viewmodels do not call the CLI directly
- use cases do not create infrastructure
- adapters do not format UI
- new UI behavior should be represented in `ConsoleScreenState`
- `ConsoleScreen` should coordinate Views instead of owning their render caches
- Views may skip redundant rendering, but must not become an independent source of application state
- resize-sensitive Views own their visual invalidation
- reducers should consume normalized events, not raw transport payloads
- blocking infrastructure calls must be offloaded before they can affect UI responsiveness
- code style contracts live in [`rules-code-style.md`](rules-code-style.md)
