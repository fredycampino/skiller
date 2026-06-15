from __future__ import annotations

import shlex
from dataclasses import dataclass
from enum import StrEnum

from stui.port.event_models import ActionPostArg
from stui.port.event_port import EventsPort, LogEventsListener
from stui.port.run_port import RunPort, RunRuntimeStatusKind
from stui.port.session_store_port import SessionStorePort, StoredSession
from stui.usecase.run_event_context import RunEventContext, RunStatus
from stui.viewmodel.console_screen_state import (
    ActionPostItem,
    ConsoleScreenState,
    RunFinishedItem,
    ViewStatusKind,
)
from stui.viewmodel.port_to_viewmodel import to_run_status


class LoadSessionFromPostStatus(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    LOADED = "loaded"
    INTRO_REQUIRED = "intro_required"
    ERROR = "error"


@dataclass(frozen=True)
class LoadSessionFromPostResult:
    status: LoadSessionFromPostStatus
    state: ConsoleScreenState


@dataclass(frozen=True)
class LoadSessionFromPostUseCase:
    run_port: RunPort
    events_port: EventsPort
    session_store_port: SessionStorePort
    context: RunEventContext

    def execute(
        self,
        observer: LogEventsListener,
        *,
        state: ConsoleScreenState,
    ) -> LoadSessionFromPostResult:
        action = _latest_auto_load_session_action(state)
        if action is None:
            return LoadSessionFromPostResult(
                status=LoadSessionFromPostStatus.NOT_APPLICABLE,
                state=state,
            )

        if action.uid in self.context.actions_done:
            return LoadSessionFromPostResult(
                status=LoadSessionFromPostStatus.NOT_APPLICABLE,
                state=state,
            )

        run_id = _param_value(action.params, "run_id")
        if not run_id:
            self.context.actions_done.add(action.uid)
            return LoadSessionFromPostResult(
                status=LoadSessionFromPostStatus.INTRO_REQUIRED,
                state=state,
            )

        runtime_status = self.run_port.status(run_id)
        if runtime_status is None:
            state.set_status(
                kind=ViewStatusKind.ERROR,
                message=f"Run '{run_id}' not found",
            )
            return LoadSessionFromPostResult(
                status=LoadSessionFromPostStatus.ERROR,
                state=state,
            )

        if runtime_status.status not in {
            RunRuntimeStatusKind.WAITING,
            RunRuntimeStatusKind.RUNNING,
        }:
            state.set_status(
                kind=ViewStatusKind.ERROR,
                message=f"Run '{run_id}' is not waiting",
            )
            return LoadSessionFromPostResult(
                status=LoadSessionFromPostStatus.ERROR,
                state=state,
            )

        run_status = to_run_status(runtime_status)
        state.load_session(run_id=run_id)
        self.session_store_port.write(StoredSession(run_id=run_id, run_name=""))
        state.set_transcript(mode=state.transcript.mode, items=[])
        state.set_prompt(
            waiting_prompt=runtime_status.prompt,
        )
        if run_status in {
            RunStatus.WAITING_INPUT,
            RunStatus.WAITING_WEBHOOK,
            RunStatus.WAITING_CHANNEL,
        }:
            state.set_status(kind=ViewStatusKind.WAITING)
        else:
            state.set_status(kind=ViewStatusKind.RUNNING)
        self.context.activate_run(run_id, run_name="", status=run_status)
        self.events_port.subscribe(run_id=run_id, listener=observer)
        self.context.actions_done.add(action.uid)
        return LoadSessionFromPostResult(
            status=LoadSessionFromPostStatus.LOADED,
            state=state,
        )


def _latest_auto_load_session_action(state: ConsoleScreenState) -> ActionPostItem | None:
    for item in reversed(state.transcript.items):
        if not isinstance(item, RunFinishedItem):
            continue
        action = item.action
        if not isinstance(action, ActionPostItem):
            continue
        if action.arg != ActionPostArg.LOAD_SESSION:
            continue
        if not action.auto:
            continue
        return action
    return None


def _param_value(params: str | None, key: str) -> str:
    if not params:
        return ""
    prefix = f"{key}="
    for part in shlex.split(params):
        if part.startswith(prefix):
            return part[len(prefix) :].strip()
    return ""
