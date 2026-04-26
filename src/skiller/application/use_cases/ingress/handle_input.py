from dataclasses import dataclass

from skiller.application.ports.external_event_store_port import ExternalEventStorePort
from skiller.application.ports.run_store_port import RunStorePort
from skiller.application.ports.runtime_event_store_port import RuntimeEventStorePort
from skiller.domain.run.run_model import RunStatus
from skiller.domain.step.skill_step_model import find_skill_step
from skiller.domain.step.step_type import StepType
from skiller.domain.wait.match_type import MatchType
from skiller.domain.wait.source_type import SourceType


@dataclass(frozen=True)
class HandleInputResult:
    accepted: bool
    run_ids: list[str]
    event_id: str | None = None
    error: str | None = None


class HandleInputUseCase:
    def __init__(
        self,
        run_store: RunStorePort,
        external_event_store: ExternalEventStorePort,
        runtime_event_store: RuntimeEventStorePort,
    ) -> None:
        self.run_store = run_store
        self.external_event_store = external_event_store
        self.runtime_event_store = runtime_event_store

    def execute(self, run_id: str, *, text: str) -> HandleInputResult:
        if not run_id:
            return HandleInputResult(accepted=False, run_ids=[], error="run_id is required")
        if not text:
            return HandleInputResult(accepted=False, run_ids=[], error="text is required")

        run = self.run_store.get_run(run_id)
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
        event_id = self.external_event_store.create_external_event(
            source_type=SourceType.INPUT,
            source_name="manual",
            match_type=MatchType.RUN,
            match_key=run_id,
            run_id=run_id,
            step_id=run.current,
            payload=payload,
        )
        self.runtime_event_store.append_event(
            "INPUT_RECEIVED",
            {"step": run.current, "payload": payload},
            run_id=run_id,
        )
        return HandleInputResult(
            accepted=True,
            run_ids=[run_id],
            event_id=event_id,
        )
