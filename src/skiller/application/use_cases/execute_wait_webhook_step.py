from skiller.application.ports.state_store_port import StateStorePort
from skiller.application.use_cases.render_current_step import CurrentStep
from skiller.application.use_cases.step_execution_result import (
    StepAdvance,
    StepExecutionStatus,
)
from skiller.domain.external_event_type import ExternalEventType
from skiller.domain.run_model import RunStatus
from skiller.domain.step_execution_model import StepExecution, WaitWebhookOutput
from skiller.domain.wait_type import WaitType


class ExecuteWaitWebhookStepUseCase:
    def __init__(self, store: StateStorePort) -> None:
        self.store = store

    def execute(self, current_step: CurrentStep) -> StepAdvance:
        step = current_step.step
        step_id = current_step.step_id
        webhook = str(step.get("webhook", "")).strip()
        key = str(step.get("key", "")).strip()

        if not webhook:
            raise ValueError(f"Step '{step_id}' requires webhook")
        if not key:
            raise ValueError(f"Step '{step_id}' requires key")

        active_wait = self.store.get_active_wait(
            current_step.run_id,
            step_id,
            wait_type=WaitType.WEBHOOK,
        )
        since_created_at = str(active_wait["created_at"]) if active_wait is not None else None
        webhook_event = self.store.get_latest_external_event(
            event_type=ExternalEventType.WEBHOOK,
            webhook=webhook,
            key=key,
            since_created_at=since_created_at,
        )

        if webhook_event is not None:
            payload = webhook_event.get("payload")
            if not isinstance(payload, dict):
                payload = None
            execution = StepExecution(
                step_type=current_step.step_type,
                input={"webhook": webhook, "key": key},
                evaluation={},
                output=WaitWebhookOutput(
                    text=f"Webhook received: {webhook}:{key}.",
                    webhook=webhook,
                    key=key,
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
                wait_type=WaitType.WEBHOOK,
                webhook=webhook,
                key=key,
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
                input={"webhook": webhook, "key": key},
                evaluation={},
                output=WaitWebhookOutput(
                    text=f"Waiting webhook: {webhook}:{key}.",
                    webhook=webhook,
                    key=key,
                ),
            ),
        )
