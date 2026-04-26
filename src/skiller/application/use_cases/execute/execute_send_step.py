from skiller.application.ports.channel_sender_port import ChannelSenderPort
from skiller.application.ports.run_store_port import RunStorePort
from skiller.application.use_cases.render.render_current_step import CurrentStep
from skiller.application.use_cases.shared.step_execution_result import (
    StepAdvance,
    StepExecutionStatus,
)
from skiller.domain.run.run_model import RunStatus
from skiller.domain.step.step_execution_model import SendOutput, StepExecution


class ExecuteSendStepUseCase:
    def __init__(
        self,
        store: RunStorePort,
        channel_sender: ChannelSenderPort,
    ) -> None:
        self.store = store
        self.channel_sender = channel_sender

    def execute(self, current_step: CurrentStep) -> StepAdvance:
        step_id = current_step.step_id
        step = current_step.step
        context = current_step.context

        channel = str(step.get("channel", "")).strip()
        key = str(step.get("key", "")).strip()
        message = str(step.get("message", "")).strip()

        if not channel:
            raise ValueError(f"Step '{step_id}' requires channel")
        if not key:
            raise ValueError(f"Step '{step_id}' requires key")
        if not message:
            raise ValueError(f"Step '{step_id}' requires message")

        send_result = self.channel_sender.send_text(
            channel=channel,
            key=key,
            message=message,
        )
        execution = StepExecution(
            step_type=current_step.step_type,
            input={
                "channel": channel,
                "key": key,
                "message": message,
            },
            evaluation={},
            output=SendOutput(
                text=f"Message sent: {send_result.channel}:{send_result.key}.",
                channel=send_result.channel,
                key=send_result.key,
                message=send_result.message,
                message_id=send_result.message_id,
            ),
        )
        context.step_executions[step_id] = execution

        raw_next = step.get("next")
        if raw_next is None:
            self.store.update_run(
                current_step.run_id,
                status=RunStatus.RUNNING,
                context=context,
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
            context=context,
        )
        return StepAdvance(
            status=StepExecutionStatus.NEXT,
            next_step_id=next_step_id,
            execution=execution,
        )
