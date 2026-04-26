import pytest

from skiller.application.ports.channel_sender_port import ChannelSendResult
from skiller.application.use_cases.execute.execute_send_step import ExecuteSendStepUseCase
from skiller.application.use_cases.render.render_current_step import CurrentStep, StepType
from skiller.application.use_cases.shared.step_execution_result import StepExecutionStatus
from skiller.domain.run_context_model import RunContext
from skiller.domain.run_model import RunStatus
from skiller.domain.step_execution_model import SendOutput

pytestmark = pytest.mark.unit


class _FakeStore:
    def __init__(self) -> None:
        self.updated_runs: list[dict[str, object]] = []

    def update_run(self, run_id: str, *, status=None, current=None, context=None) -> None:  # noqa: ANN001
        self.updated_runs.append(
            {
                "run_id": run_id,
                "status": status,
                "current": current,
                "context": context,
            }
        )


class _FakeChannelSender:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def send_text(self, *, channel: str, key: str, message: str) -> ChannelSendResult:
        self.calls.append(
            {
                "channel": channel,
                "key": key,
                "message": message,
            }
        )
        return ChannelSendResult(
            channel=channel,
            key=key,
            message=message,
            message_id="msg-1",
        )


def _build_current_step(step: dict[str, object]) -> CurrentStep:
    return CurrentStep(
        run_id="run-1",
        step_index=0,
        step_id="reply_whatsapp",
        step_type=StepType.SEND,
        step=step,
        context=RunContext(inputs={}, step_executions={}),
    )


def test_send_moves_current_to_explicit_next() -> None:
    store = _FakeStore()
    channel_sender = _FakeChannelSender()
    use_case = ExecuteSendStepUseCase(store=store, channel_sender=channel_sender)
    current_step = _build_current_step(
        {"channel": "whatsapp", "key": "chat-1", "message": "hola", "next": "done"}
    )

    result = use_case.execute(current_step)

    assert result.status == StepExecutionStatus.NEXT
    assert result.next_step_id == "done"
    assert result.execution is not None
    assert result.execution.output == SendOutput(
        text="Message sent: whatsapp:chat-1.",
        channel="whatsapp",
        key="chat-1",
        message="hola",
        message_id="msg-1",
    )
    assert current_step.context.step_executions["reply_whatsapp"] == result.execution
    assert channel_sender.calls == [
        {
            "channel": "whatsapp",
            "key": "chat-1",
            "message": "hola",
        }
    ]
    assert store.updated_runs == [
        {
            "run_id": "run-1",
            "status": RunStatus.RUNNING,
            "current": "done",
            "context": current_step.context,
        }
    ]


def test_send_marks_completed_when_next_is_missing() -> None:
    store = _FakeStore()
    channel_sender = _FakeChannelSender()
    use_case = ExecuteSendStepUseCase(store=store, channel_sender=channel_sender)
    current_step = _build_current_step(
        {"channel": "whatsapp", "key": "chat-1", "message": "hola"}
    )

    result = use_case.execute(current_step)

    assert result.status == StepExecutionStatus.COMPLETED
    assert result.next_step_id is None
    assert result.execution is not None
    assert result.execution.output == SendOutput(
        text="Message sent: whatsapp:chat-1.",
        channel="whatsapp",
        key="chat-1",
        message="hola",
        message_id="msg-1",
    )
    assert store.updated_runs == [
        {
            "run_id": "run-1",
            "status": RunStatus.RUNNING,
            "current": None,
            "context": current_step.context,
        }
    ]


def test_send_rejects_empty_next_when_declared() -> None:
    store = _FakeStore()
    channel_sender = _FakeChannelSender()
    use_case = ExecuteSendStepUseCase(store=store, channel_sender=channel_sender)
    current_step = _build_current_step(
        {"channel": "whatsapp", "key": "chat-1", "message": "hola", "next": "   "}
    )

    with pytest.raises(ValueError, match="requires non-empty next"):
        use_case.execute(current_step)
