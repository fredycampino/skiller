# TUI Architecture

## Architecture

Current shape:

```text
ConsoleScreen
-> ConsoleScreenViewModel
-> RunPort
-> DefaultRunPort
   -> CliRunAdapter
   -> PollingEventObserver
   -> RunEventMapper
-> skiller CLI
```

High-level block flows:

```text
Dispatch / command flow

[ConsoleScreen] -> [ConsoleScreenViewModel] -> [RunPort] -> [CliRunAdapter] -> [skiller CLI]


Observation / event flow

[skiller CLI] -> [PollingEventObserver] -> [RunEventMapper] -> [RunPort] -> [ConsoleScreenViewModel] -> [ConsoleScreen]
```

Current UI shape:

```text
[TranscriptLog / RichLog]
[ScreenStatusView]
[Prompt]
[Footer]
```

The TUI is separated into:
- `screen`
- `viewmodel`
- `port`
- `adapter`

## Components

### `ConsoleScreen`
- Textual screen
- captures keyboard input
- owns widgets and screen lifecycle
- refreshes the UI from `ConsoleScreenState`

### `ScreenStatusView`
- global visual status component
- renders `ScreenStatus`
- owns the running spinner animation locally
- does not render run-local status; run status stays in the transcript

### `ConsoleScreenViewModel`
- presentation logic
- handles `/run` and `/quit`
- subscribes to run observation
- transforms observed runtime events into UI state
- the visual output is modeled as UI state, not raw logs
- exposes global `ScreenStatus` for the status view

### `RunPort`
- output boundary of the TUI
- defines command dispatch and observation subscription

### `DefaultRunPort`
- concrete composition of the port
- delegates command dispatch to `CliRunAdapter`
- delegates observation to `PollingEventObserver`

### `CliRunAdapter`
- executes `python -m skiller ...`
- maps the immediate command result to `CommandAck`

### `PollingEventObserver`
- polls `status` and `logs`
- notifies the subscribed observer with batches of `PollingEvent`

### `RunEventMapper`
- converts raw `status/logs` payloads into structured `PollingEvent`
- does not own UI formatting

## Actions And Events

### Dispatch Flow

```text
user types /run ...
-> ConsoleScreen.action_submit()
-> ConsoleScreenViewModel.submit()
-> RunPort.run()
-> CliRunAdapter.run()
-> skiller CLI
-> CommandAck
-> ConsoleScreenViewModel updates state
-> ConsoleScreen refreshes
```

### Observation Flow

```text
ConsoleScreenViewModel.start_observing(run_id)
-> RunPort.subscribe(observer)
-> PollingEventObserver.subscribe(observer)
-> polling loop
   -> skiller status
   -> skiller logs
   -> RunEventMapper
   -> list[PollingEvent]
-> observer.notify(events)
-> ConsoleScreenViewModel updates ConsoleScreenState
-> ConsoleScreen refreshes
```

## UI / Screen

Responsibilities:
- build the screen layout
- own prompt, transcript, status and footer widgets
- submit prompt text to the viewmodel
- apply `ConsoleScreenState` to the widgets
- keep UI concerns local, such as scroll actions and focus

## ViewModel

Responsibilities:
- parse user intent at presentation level
- coordinate command dispatch
- start and stop observation
- update `ConsoleScreenState`
- produce transcript items for the UI
- produce `ScreenStatus` for the global status view

Important point:
- visual output is already modeled as UI state through `TranscriptItem[]`
- the screen renders transcript items, not raw runtime log strings directly
- the global status view renders `ScreenStatus`, not free-form status strings

## Port / Adapter

Responsibilities:

### Port
- define what the TUI asks from the outside world
- keep the screen and viewmodel isolated from the concrete runtime transport

### Adapters
- execute the real CLI command
- poll and observe runtime progress
- map external payloads into neutral `PollingEvent`
- keep runtime transport details out of the UI layer
