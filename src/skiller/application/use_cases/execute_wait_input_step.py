from skiller.application.ports.state_store_port import StateStorePort
from skiller.application.use_cases.render_current_step import CurrentStep
from skiller.application.use_cases.step_execution_result import (
    StepExecutionResult,
    StepExecutionStatus,
    WaitInputResult,
)
from skiller.domain.run_model import RunStatus


class ExecuteWaitInputStepUseCase:
    def __init__(self, store: StateStorePort) -> None:
        self.store = store

    def execute(self, current_step: CurrentStep) -> StepExecutionResult:
        step = current_step.step
        step_id = current_step.step_id
        prompt = str(step.get("prompt", "")).strip()

        if not prompt:
            raise ValueError(f"Step '{step_id}' requires prompt")

        active_wait = self.store.get_active_input_wait(current_step.run_id, step_id)
        since_created_at = str(active_wait["created_at"]) if active_wait is not None else None
        input_event = self.store.get_latest_input_event(
            current_step.run_id,
            step_id,
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

            current_step.context.results[step_id] = {
                "ok": True,
                "prompt": prompt,
                "payload": payload,
                "input_event_id": str(input_event.get("id", "")).strip(),
            }
            if active_wait is not None:
                self.store.resolve_input_wait(str(active_wait["id"]))

            raw_next = step.get("next")
            if raw_next is None:
                self.store.update_run(
                    current_step.run_id,
                    status=RunStatus.RUNNING,
                    context=current_step.context,
                )
                return StepExecutionResult(
                    status=StepExecutionStatus.COMPLETED,
                    result=WaitInputResult(
                        prompt=prompt,
                        payload=payload,
                        input_event_id=str(input_event.get("id", "")).strip() or None,
                    ),
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
            return StepExecutionResult(
                status=StepExecutionStatus.NEXT,
                next_step_id=next_step_id,
                result=WaitInputResult(
                    prompt=prompt,
                    payload=payload,
                    input_event_id=str(input_event.get("id", "")).strip() or None,
                ),
            )

        if active_wait is None:
            self.store.create_input_wait(current_step.run_id, step_id)
        self.store.update_run(
            current_step.run_id,
            status=RunStatus.WAITING,
            current=step_id,
            context=current_step.context,
        )
        return StepExecutionResult(
            status=StepExecutionStatus.WAITING,
            result=WaitInputResult(prompt=prompt),
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

        resolved = current_step.context.results.get(step_id)
        if not isinstance(resolved, dict):
            return False

        consumed_input_event_id = str(resolved.get("input_event_id", "")).strip()
        return consumed_input_event_id == input_event_id
