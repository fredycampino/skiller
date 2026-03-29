from dataclasses import dataclass

from skiller.application.ports.state_store_port import StateStorePort
from skiller.domain.external_event_type import ExternalEventType
from skiller.domain.run_model import RunStatus
from skiller.domain.skill_step_model import find_skill_step
from skiller.domain.step_type import StepType


@dataclass(frozen=True)
class HandleInputResult:
    accepted: bool
    run_ids: list[str]
    event_id: str | None = None
    error: str | None = None


class HandleInputUseCase:
    def __init__(self, store: StateStorePort) -> None:
        self.store = store

    def execute(self, run_id: str, *, text: str) -> HandleInputResult:
        if not run_id:
            return HandleInputResult(accepted=False, run_ids=[], error="run_id is required")
        if not text:
            return HandleInputResult(accepted=False, run_ids=[], error="text is required")

        run = self.store.get_run(run_id)
        if run is None:
            return HandleInputResult(accepted=False, run_ids=[], error=f"Run '{run_id}' not found")
        if run.status != RunStatus.WAITING.value:
            return HandleInputResult(
                accepted=False,
                run_ids=[],
                error=f"Run '{run_id}' is not waiting",
            )
        if not run.current:
            return HandleInputResult(
                accepted=False,
                run_ids=[],
                error=f"Run '{run_id}' does not have a current step",
            )

        raw_steps = run.skill_snapshot.get("steps", [])
        try:
            _, current_step = find_skill_step(raw_steps, run.current)
        except ValueError:
            return HandleInputResult(
                accepted=False,
                run_ids=[],
                error=f"Run '{run_id}' current step '{run.current}' was not found",
            )

        if current_step.step_type != StepType.WAIT_INPUT:
            return HandleInputResult(
                accepted=False,
                run_ids=[],
                error=f"Run '{run_id}' current step '{run.current}' is not wait_input",
            )

        payload = {"text": text}
        event_id = self.store.create_external_event(
            event_type=ExternalEventType.INPUT,
            run_id=run_id,
            step_id=run.current,
            payload=payload,
        )
        self.store.append_event(
            "INPUT_RECEIVED",
            {"step": run.current, "payload": payload},
            run_id=run_id,
        )
        return HandleInputResult(
            accepted=True,
            run_ids=[run_id],
            event_id=event_id,
        )
