# TUI Architecture

## Purpose

This document explains the architectural patterns used by the TUI. It does not document command syntax or command semantics. Those live in [`../../../packages/skiller/docs/cli/command-guide.md`](../../../packages/skiller/docs/cli/command-guide.md).

## Core Patterns

### `State-driven UI`
- the screen renders `ConsoleScreenState`
- the UI does not render raw runtime payloads directly
- transcript, prompt, autocomplete, status, and runs table are all presentation state

### `ViewModel as Orchestrator`
- the screen emits user intent
- the viewmodel decides which use case to call
- the viewmodel emits the updated state back to the screen

### `Use Case per Interaction`
- each interaction is handled by a focused use case
- use cases expose `execute(...)`
- use cases receive dependencies through `port` or `context`
- use cases return state or result data to the viewmodel

### `Ports and Adapters Boundary`
- ports define what the TUI needs from the outside world
- adapters implement those contracts against the CLI/runtime
- the viewmodel and screen do not talk to subprocess or polling code directly

### `Event Reduction`
- runtime status and logs are converted into normalized events
- normalized events are reduced into presentation state
- the reducer is responsible for transcript-ready state updates

### `Blocking I/O Offloading`
- blocking runtime calls use `asyncio.to_thread(...)`
- the async UI loop stays responsive while the CLI is queried

## State Model

`ConsoleScreenState` is the central UI contract.

It holds:
- `transcript_items`
- `screen_status`
- `waiting_prompt`
- `prompt_text`
- `prompt_cursor_position`
- `autocompletion`
- `runs`
- `runs_table_visible`
- `session_key`

This keeps rendering decisions in one place and allows the screen to re-render from state instead of from runtime responses.

## Layer Responsibilities

### `Screen`
- owns Textual widgets and lifecycle
- captures keyboard input and focus changes
- forwards intent to the viewmodel
- renders widgets from `ConsoleScreenState`

### `ViewModel`
- orchestrates presentation behavior
- coordinates dispatch, query, waiting input, autocomplete, and observation
- updates and emits `ConsoleScreenState`

### `UseCase`
- owns one interaction or transformation
- applies presentation rules outside the screen
- stays small and directly testable

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
-> skiller CLI
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
-> skiller CLI
-> ViewModel emits state
-> Screen re-renders
```

### `Observation pattern`

```text
PollingEventObserver
-> RunEventMapper
-> PollingEventReducerUseCase
-> ViewModel emits state
-> Screen re-renders
```

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
-> updates `runs_table_visible`
-> screen shows or hides `RunsTableView`
```

## Current Mapping

- `State-driven UI` -> `ConsoleScreen`, `ConsoleScreenState`
- `ViewModel as Orchestrator` -> `ConsoleScreenViewModel`
- `Use Case per Interaction` -> `RunCommandUseCase`, `ListRunsUseCase`, `PromptEnterUseCase`, `AutocompleteUseCase`, `MoveCompletionUseCase`, `SubmitWaitingInputUseCase`, `PollingEventReducerUseCase`
- `Ports and Adapters Boundary` -> `RunPort`, `RunsPort`, `DefaultRunPort`, `DefaultRunsPort`, `CliRunAdapter`, `CliRunsAdapter`
- `Event Reduction` -> `PollingEventObserver`, `RunEventMapper`, `PollingEventReducerUseCase`

## Design Rules

- screens do not make business decisions
- viewmodels do not call the CLI directly
- use cases do not create infrastructure
- adapters do not format UI
- new UI behavior should be represented in `ConsoleScreenState`
