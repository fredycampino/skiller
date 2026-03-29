from skiller.application.ports.state_store_port import StateStorePort
from skiller.application.use_cases.render_current_step import CurrentStep
from skiller.application.use_cases.step_execution_result import (
    StepAdvance,
    StepExecutionStatus,
)
from skiller.domain.external_event_type import ExternalEventType
from skiller.domain.run_model import RunStatus
from skiller.domain.step_execution_model import StepExecution, WaitInputOutput
from skiller.domain.wait_type import WaitType


class ExecuteWaitInputStepUseCase:
    def __init__(self, store: StateStorePort) -> None:
        self.store = store

    def execute(self, current_step: CurrentStep) -> StepAdvance:
        step = current_step.step
        step_id = current_step.step_id
        prompt = str(step.get("prompt", "")).strip()

        if not prompt:
            raise ValueError(f"Step '{step_id}' requires prompt")

        active_wait = self.store.get_active_wait(
            current_step.run_id,
            step_id,
            wait_type=WaitType.INPUT,
        )
        since_created_at = str(active_wait["created_at"]) if active_wait is not None else None
        input_event = self.store.get_latest_external_event(
            event_type=ExternalEventType.INPUT,
            run_id=current_step.run_id,
            step_id=step_id,
            since_created_at=since_created_at,
        )
        if input_event is not None and self._is_already_consumed(
            current_step=current_step,
            step_id=step_id,
            input_event_id=str(input_event.get("id", "")).strip(),
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
                self.store.resolve_wait(str(active_wait["id"]))

            raw_next = step.get("next")
            if raw_next is None:
                self.store.update_run(
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

            self.store.update_run(
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
            self.store.create_wait(
                current_step.run_id,
                step_id=step_id,
                wait_type=WaitType.INPUT,
            )
        self.store.update_run(
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
