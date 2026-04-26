from skiller.application.ports.external_event_store_port import ExternalEventStorePort
from skiller.application.ports.run_store_port import RunStorePort
from skiller.application.ports.wait_store_port import WaitStorePort
from skiller.application.use_cases.render.render_current_step import CurrentStep
from skiller.application.use_cases.shared.step_execution_result import (
    StepAdvance,
    StepExecutionStatus,
)
from skiller.domain.run.run_model import RunStatus
from skiller.domain.step.step_execution_model import StepExecution, WaitInputOutput
from skiller.domain.wait.match_type import MatchType
from skiller.domain.wait.source_type import SourceType
from skiller.domain.wait.wait_type import WaitType


class ExecuteWaitInputStepUseCase:
    def __init__(
        self,
        run_store: RunStorePort,
        wait_store: WaitStorePort,
        external_event_store: ExternalEventStorePort,
    ) -> None:
        self.run_store = run_store
        self.wait_store = wait_store
        self.external_event_store = external_event_store

    def execute(self, current_step: CurrentStep) -> StepAdvance:
        step = current_step.step
        step_id = current_step.step_id
        prompt = str(step.get("prompt", "")).strip()

        if not prompt:
            raise ValueError(f"Step '{step_id}' requires prompt")

        active_wait = self.wait_store.get_active_wait(
            current_step.run_id,
            step_id,
            wait_type=WaitType.INPUT,
        )
        input_event = self.external_event_store.get_latest_external_event(
            source_type=SourceType.INPUT,
            source_name="manual",
            match_type=MatchType.RUN,
            match_key=current_step.run_id,
            run_id=current_step.run_id,
            step_id=step_id,
            since_created_at=current_step.run_created_at,
        )
        if input_event is not None and self._is_already_consumed(
            current_step=current_step,
            step_id=step_id,
            input_event_id=str(input_event.get("id", "")).strip(),
        ):
            input_event = None

        if input_event is not None:
            input_event_id = str(input_event.get("id", "")).strip()
            if not input_event_id:
                input_event = None
            elif not self.external_event_store.consume_external_event(
                input_event_id,
                run_id=current_step.run_id,
            ):
                input_event = None

        if input_event is not None:
            payload = input_event.get("payload", {})
            if not isinstance(payload, dict):
                payload = {}

            input_event_id = str(input_event.get("id", "")).strip() or None
            execution = StepExecution(
                step_type=current_step.step_type,
                input={"prompt": prompt},
                evaluation={"input_event_id": input_event_id},
                output=WaitInputOutput(
                    text="Input received.",
                    prompt=prompt,
                    payload=payload,
                ),
            )
            current_step.context.step_executions[step_id] = execution
            if active_wait is not None:
                self.wait_store.resolve_wait(str(active_wait["id"]))

            raw_next = step.get("next")
            if raw_next is None:
                self.run_store.update_run(
                    current_step.run_id,
                    status=RunStatus.RUNNING,
                    context=current_step.context,
                )
                return StepAdvance(
                    status=StepExecutionStatus.COMPLETED,
                    execution=execution,
                )

            next_step_id = str(raw_next).strip()
            if not next_step_id:
                raise ValueError(f"Step '{step_id}' requires non-empty next")

            self.run_store.update_run(
                current_step.run_id,
                status=RunStatus.RUNNING,
                current=next_step_id,
                context=current_step.context,
            )
            return StepAdvance(
                status=StepExecutionStatus.NEXT,
                next_step_id=next_step_id,
                execution=execution,
            )

        if active_wait is None:
            self.wait_store.create_wait(
                current_step.run_id,
                step_id=step_id,
                wait_type=WaitType.INPUT,
                source_type=SourceType.INPUT,
                source_name="manual",
                match_type=MatchType.RUN,
                match_key=current_step.run_id,
            )
        self.run_store.update_run(
            current_step.run_id,
            status=RunStatus.WAITING,
            current=step_id,
            context=current_step.context,
        )
        return StepAdvance(
            status=StepExecutionStatus.WAITING,
            execution=StepExecution(
                step_type=current_step.step_type,
                input={"prompt": prompt},
                evaluation={},
                output=WaitInputOutput(text=prompt, prompt=prompt),
            ),
        )

    def _is_already_consumed(
        self,
        *,
        current_step: CurrentStep,
        step_id: str,
        input_event_id: str,
    ) -> bool:
        if not input_event_id:
            return False

        resolved = current_step.context.step_executions.get(step_id)
        if resolved is None:
            return False

        consumed_input_event_id = str(resolved.evaluation.get("input_event_id", "")).strip()
        return consumed_input_event_id == input_event_id
