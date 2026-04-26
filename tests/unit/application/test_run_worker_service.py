from dataclasses import dataclass

import pytest

from skiller.application.run_worker_service import RunWorkerService, RunWorkerStatus
from skiller.application.use_cases.render.render_current_step import (
    CurrentStep,
    CurrentStepStatus,
    RenderCurrentStepResult,
    StepType,
)
from skiller.application.use_cases.render.render_mcp_config import RenderMcpConfigStatus
from skiller.application.use_cases.run.append_runtime_event import RuntimeEventType
from skiller.application.use_cases.shared.step_execution_result import (
    StepAdvance,
    StepExecutionStatus,
)
from skiller.domain.run_context_model import RunContext
from skiller.domain.step_execution_model import (
    NotifyOutput,
    SendOutput,
    ShellOutput,
    StepExecution,
    WaitInputOutput,
    WaitWebhookOutput,
)
from skiller.domain.step_type import StepType as DomainStepType

pytestmark = pytest.mark.unit


class _FakeRenderCurrentStepUseCase:
    def __init__(self, results: list[RenderCurrentStepResult]) -> None:
        self.results = list(results)
        self.calls: list[str] = []

    def execute(self, run_id: str) -> RenderCurrentStepResult:
        self.calls.append(run_id)
        if not self.results:
            raise AssertionError("No render results left")
        return self.results.pop(0)


class _FakeCompleteRunUseCase:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def execute(self, run_id: str) -> None:
        self.calls.append(run_id)


class _FakeFailRunUseCase:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def execute(self, run_id: str, *, error: str) -> None:
        self.calls.append({"run_id": run_id, "error": error})


class _FakeAppendRuntimeEventUseCase:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def execute(
        self,
        run_id: str,
        *,
        event_type: RuntimeEventType,
        payload: dict[str, object] | None = None,
        step_id: str | None = None,
        step_type: DomainStepType | None = None,
        execution: StepExecution | None = None,
        next_step_id: str | None = None,
        error: str | None = None,
    ) -> None:
        event_payload = dict(payload or {})
        if step_id is not None:
            event_payload["step"] = step_id
        if step_type is not None:
            event_payload["step_type"] = step_type.value
        if execution is not None:
            event_payload["step_type"] = execution.step_type.value
            event_payload["output"] = execution.to_public_output_dict()
        if next_step_id is not None:
            event_payload["next"] = next_step_id
        if error is not None:
            event_payload["error"] = error
        self.calls.append(
            {
                "run_id": run_id,
                "event_type": event_type,
                "payload": event_payload,
            }
        )


class _FakeStepUseCase:
    def __init__(
        self,
        results: list[StepAdvance] | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.results = list(results or [])
        self.error = error
        self.calls: list[CurrentStep] = []

    def execute(self, current_step: CurrentStep) -> StepAdvance:
        self.calls.append(current_step)
        if self.error is not None:
            raise self.error
        if not self.results:
            raise AssertionError("No step execution results left")
        return self.results.pop(0)


class _FakeMcpStepUseCase:
    def __init__(self, result: StepAdvance) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def execute(self, current_step: CurrentStep, mcp_config: object) -> StepAdvance:
        self.calls.append({"current_step": current_step, "mcp_config": mcp_config})
        return self.result


@dataclass(frozen=True)
class _FakeRenderMcpConfigResult:
    status: RenderMcpConfigStatus
    mcp_config: object | None = None
    error: str | None = None


class _FakeRenderMcpConfigUseCase:
    def __init__(self, result: _FakeRenderMcpConfigResult | None = None) -> None:
        self.result = result or _FakeRenderMcpConfigResult(
            status=RenderMcpConfigStatus.RENDERED,
            mcp_config={"transport": "stdio"},
        )
        self.calls: list[CurrentStep] = []

    def execute(self, current_step: CurrentStep) -> _FakeRenderMcpConfigResult:
        self.calls.append(current_step)
        return self.result


@dataclass(frozen=True)
class _UnknownStepType:
    value: str


def _build_current_step(
    step_type: StepType | _UnknownStepType, *, step_id: str = "start"
) -> CurrentStep:
    return CurrentStep(
        run_id="run-1",
        step_index=0,
        step_id=step_id,
        step_type=step_type,  # type: ignore[arg-type]
        step={},
        context=RunContext(inputs={}, step_executions={}),
    )


def _build_service(
    *,
    render_results: list[RenderCurrentStepResult],
    agent_results: list[StepAdvance] | None = None,
    notify_results: list[StepAdvance] | None = None,
    send_results: list[StepAdvance] | None = None,
    shell_results: list[StepAdvance] | None = None,
    input_wait_results: list[StepAdvance] | None = None,
    wait_results: list[StepAdvance] | None = None,
    mcp_render_result: _FakeRenderMcpConfigResult | None = None,
    notify_error: Exception | None = None,
) -> tuple[RunWorkerService, _FakeCompleteRunUseCase, _FakeFailRunUseCase]:
    complete_run_use_case = _FakeCompleteRunUseCase()
    fail_run_use_case = _FakeFailRunUseCase()
    append_runtime_event_use_case = _FakeAppendRuntimeEventUseCase()
    service = RunWorkerService(
        complete_run_use_case=complete_run_use_case,
        fail_run_use_case=fail_run_use_case,
        append_runtime_event_use_case=append_runtime_event_use_case,
        render_current_step_use_case=_FakeRenderCurrentStepUseCase(render_results),
        render_mcp_config_use_case=_FakeRenderMcpConfigUseCase(mcp_render_result),
        execute_agent_step_use_case=_FakeStepUseCase(agent_results),
        execute_assign_step_use_case=_FakeStepUseCase(),
        execute_llm_prompt_step_use_case=_FakeStepUseCase(),
        execute_mcp_step_use_case=_FakeMcpStepUseCase(
            StepAdvance(status=StepExecutionStatus.COMPLETED)
        ),
        execute_notify_step_use_case=_FakeStepUseCase(notify_results, error=notify_error),
        execute_send_step_use_case=_FakeStepUseCase(send_results),
        execute_shell_step_use_case=_FakeStepUseCase(shell_results),
        execute_switch_step_use_case=_FakeStepUseCase(),
        execute_when_step_use_case=_FakeStepUseCase(),
        execute_wait_input_step_use_case=_FakeStepUseCase(input_wait_results),
        execute_wait_webhook_step_use_case=_FakeStepUseCase(wait_results),
    )
    service.append_runtime_event_use_case = append_runtime_event_use_case
    return service, complete_run_use_case, fail_run_use_case


def test_worker_returns_run_not_found() -> None:
    service, complete_run_use_case, fail_run_use_case = _build_service(
        render_results=[RenderCurrentStepResult(status=CurrentStepStatus.RUN_NOT_FOUND)],
    )

    result = service.run("run-1")

    assert result.status == RunWorkerStatus.RUN_NOT_FOUND
    assert complete_run_use_case.calls == []
    assert fail_run_use_case.calls == []


def test_worker_executes_shell_step() -> None:
    service, complete_run_use_case, fail_run_use_case = _build_service(
        render_results=[
            RenderCurrentStepResult(
                status=CurrentStepStatus.READY,
                current_step=_build_current_step(StepType.SHELL),
            ),
            RenderCurrentStepResult(status=CurrentStepStatus.DONE),
        ],
        shell_results=[
            StepAdvance(
                status=StepExecutionStatus.NEXT,
                next_step_id="done",
                execution=StepExecution(
                    step_type=StepType.SHELL,
                    output=ShellOutput(
                        text="hello",
                        ok=True,
                        exit_code=0,
                        stdout="hello\n",
                        stderr="",
                    ),
                ),
            )
        ],
    )

    result = service.run("run-1")

    assert result.status == RunWorkerStatus.SUCCEEDED
    assert complete_run_use_case.calls == ["run-1"]
    assert fail_run_use_case.calls == []
    assert service.append_runtime_event_use_case.calls[:2] == [
        {
            "run_id": "run-1",
            "event_type": RuntimeEventType.STEP_STARTED,
            "payload": {"step": "start", "step_type": "shell"},
        },
        {
            "run_id": "run-1",
            "event_type": RuntimeEventType.STEP_SUCCESS,
            "payload": {
                "step": "start",
                "step_type": "shell",
                "output": {
                    "text": "hello",
                    "value": {
                        "ok": True,
                        "exit_code": 0,
                        "stdout": "hello\n",
                        "stderr": "",
                    },
                    "body_ref": None,
                },
                "next": "done",
            },
        },
    ]


def test_worker_executes_send_step() -> None:
    service, complete_run_use_case, fail_run_use_case = _build_service(
        render_results=[
            RenderCurrentStepResult(
                status=CurrentStepStatus.READY,
                current_step=_build_current_step(StepType.SEND),
            ),
            RenderCurrentStepResult(status=CurrentStepStatus.DONE),
        ],
        send_results=[
            StepAdvance(
                status=StepExecutionStatus.NEXT,
                next_step_id="done",
                execution=StepExecution(
                    step_type=StepType.SEND,
                    output=SendOutput(
                        text="Message sent: whatsapp:chat-1.",
                        channel="whatsapp",
                        key="chat-1",
                        message="hola",
                        message_id="msg-1",
                    ),
                ),
            )
        ],
    )

    result = service.run("run-1")

    assert result.status == RunWorkerStatus.SUCCEEDED
    assert complete_run_use_case.calls == ["run-1"]
    assert fail_run_use_case.calls == []
    assert service.append_runtime_event_use_case.calls[:2] == [
        {
            "run_id": "run-1",
            "event_type": RuntimeEventType.STEP_STARTED,
            "payload": {"step": "start", "step_type": "send"},
        },
        {
            "run_id": "run-1",
            "event_type": RuntimeEventType.STEP_SUCCESS,
            "payload": {
                "step": "start",
                "step_type": "send",
                "output": {
                    "text": "Message sent: whatsapp:chat-1.",
                    "value": {
                        "channel": "whatsapp",
                        "key": "chat-1",
                        "message": "hola",
                        "message_id": "msg-1",
                    },
                    "body_ref": None,
                },
                "next": "done",
            },
        },
    ]


def test_worker_completes_run_when_renderer_reports_done() -> None:
    service, complete_run_use_case, fail_run_use_case = _build_service(
        render_results=[RenderCurrentStepResult(status=CurrentStepStatus.DONE)],
    )

    result = service.run("run-1")

    assert result.status == RunWorkerStatus.SUCCEEDED
    assert complete_run_use_case.calls == ["run-1"]
    assert fail_run_use_case.calls == []
    assert service.append_runtime_event_use_case.calls == [
        {
            "run_id": "run-1",
            "event_type": RuntimeEventType.RUN_FINISHED,
            "payload": {"status": "SUCCEEDED"},
        }
    ]


def test_worker_returns_waiting_when_wait_step_blocks() -> None:
    service, complete_run_use_case, fail_run_use_case = _build_service(
        render_results=[
            RenderCurrentStepResult(
                status=CurrentStepStatus.READY,
                current_step=_build_current_step(StepType.WAIT_WEBHOOK),
            )
        ],
        wait_results=[
            StepAdvance(
                status=StepExecutionStatus.WAITING,
                execution=StepExecution(
                    step_type=StepType.WAIT_WEBHOOK,
                    output=WaitWebhookOutput(
                        text="Waiting webhook: github:pr-1.",
                        webhook="github",
                        key="pr-1",
                    ),
                ),
            )
        ],
    )

    result = service.run("run-1")

    assert result.status == RunWorkerStatus.WAITING
    assert complete_run_use_case.calls == []
    assert fail_run_use_case.calls == []
    assert service.append_runtime_event_use_case.calls == [
        {
            "run_id": "run-1",
            "event_type": RuntimeEventType.STEP_STARTED,
            "payload": {"step": "start", "step_type": "wait_webhook"},
        },
        {
            "run_id": "run-1",
            "event_type": RuntimeEventType.RUN_WAITING,
            "payload": {
                "step": "start",
                "step_type": "wait_webhook",
                "output": {
                    "text": "Waiting webhook: github:pr-1.",
                    "value": {"webhook": "github", "key": "pr-1", "payload": None},
                    "body_ref": None,
                },
            },
        },
    ]


def test_worker_returns_waiting_when_wait_input_step_blocks() -> None:
    service, complete_run_use_case, fail_run_use_case = _build_service(
        render_results=[
            RenderCurrentStepResult(
                status=CurrentStepStatus.READY,
                current_step=_build_current_step(StepType.WAIT_INPUT),
            )
        ],
        input_wait_results=[
            StepAdvance(
                status=StepExecutionStatus.WAITING,
                execution=StepExecution(
                    step_type=StepType.WAIT_INPUT,
                    output=WaitInputOutput(
                        text="Write a message.",
                        prompt="Write a message.",
                    ),
                ),
            )
        ],
    )

    result = service.run("run-1")

    assert result.status == RunWorkerStatus.WAITING
    assert complete_run_use_case.calls == []
    assert fail_run_use_case.calls == []
    assert service.append_runtime_event_use_case.calls == [
        {
            "run_id": "run-1",
            "event_type": RuntimeEventType.STEP_STARTED,
            "payload": {"step": "start", "step_type": "wait_input"},
        },
        {
            "run_id": "run-1",
            "event_type": RuntimeEventType.RUN_WAITING,
            "payload": {
                "step": "start",
                "step_type": "wait_input",
                "output": {
                    "text": "Write a message.",
                    "value": {
                        "prompt": "Write a message.",
                        "payload": None,
                    },
                    "body_ref": None,
                },
            },
        },
    ]


def test_worker_loops_on_next_and_then_completes() -> None:
    service, complete_run_use_case, fail_run_use_case = _build_service(
        render_results=[
            RenderCurrentStepResult(
                status=CurrentStepStatus.READY,
                current_step=_build_current_step(StepType.NOTIFY, step_id="start"),
            ),
            RenderCurrentStepResult(
                status=CurrentStepStatus.READY,
                current_step=_build_current_step(StepType.NOTIFY, step_id="done"),
            ),
        ],
        notify_results=[
            StepAdvance(
                status=StepExecutionStatus.NEXT,
                next_step_id="done",
                execution=StepExecution(
                    step_type=StepType.NOTIFY,
                    output=NotifyOutput(text="first", message="first"),
                ),
            ),
            StepAdvance(
                status=StepExecutionStatus.COMPLETED,
                execution=StepExecution(
                    step_type=StepType.NOTIFY,
                    output=NotifyOutput(text="done", message="done"),
                ),
            ),
        ],
    )

    result = service.run("run-1")

    assert result.status == RunWorkerStatus.SUCCEEDED
    assert complete_run_use_case.calls == ["run-1"]
    assert fail_run_use_case.calls == []
    assert service.append_runtime_event_use_case.calls == [
        {
            "run_id": "run-1",
            "event_type": RuntimeEventType.STEP_STARTED,
            "payload": {"step": "start", "step_type": "notify"},
        },
        {
            "run_id": "run-1",
            "event_type": RuntimeEventType.STEP_SUCCESS,
            "payload": {
                "step": "start",
                "step_type": "notify",
                "output": {
                    "text": "first",
                    "value": {"message": "first"},
                    "body_ref": None,
                },
                "next": "done",
            },
        },
        {
            "run_id": "run-1",
            "event_type": RuntimeEventType.STEP_STARTED,
            "payload": {"step": "done", "step_type": "notify"},
        },
        {
            "run_id": "run-1",
            "event_type": RuntimeEventType.STEP_SUCCESS,
            "payload": {
                "step": "done",
                "step_type": "notify",
                "output": {
                    "text": "done",
                    "value": {"message": "done"},
                    "body_ref": None,
                },
            },
        },
        {
            "run_id": "run-1",
            "event_type": RuntimeEventType.RUN_FINISHED,
            "payload": {"status": "SUCCEEDED"},
        },
    ]


def test_worker_fails_invalid_skill_state() -> None:
    service, complete_run_use_case, fail_run_use_case = _build_service(
        render_results=[RenderCurrentStepResult(status=CurrentStepStatus.INVALID_SKILL)],
    )

    result = service.run("run-1")

    assert result.status == RunWorkerStatus.FAILED
    assert result.error == "Run 'run-1' is invalid: status=CurrentStepStatus.INVALID_SKILL"
    assert complete_run_use_case.calls == []
    assert fail_run_use_case.calls == [
        {
            "run_id": "run-1",
            "error": "Run 'run-1' is invalid: status=CurrentStepStatus.INVALID_SKILL",
        }
    ]


def test_worker_fails_when_step_executor_raises() -> None:
    service, complete_run_use_case, fail_run_use_case = _build_service(
        render_results=[
            RenderCurrentStepResult(
                status=CurrentStepStatus.READY,
                current_step=_build_current_step(StepType.NOTIFY),
            )
        ],
        notify_error=ValueError("notify failed"),
    )

    result = service.run("run-1")

    assert result.status == RunWorkerStatus.FAILED
    assert result.error == "notify failed"
    assert complete_run_use_case.calls == []
    assert fail_run_use_case.calls == [{"run_id": "run-1", "error": "notify failed"}]
    assert service.append_runtime_event_use_case.calls == [
        {
            "run_id": "run-1",
            "event_type": RuntimeEventType.STEP_STARTED,
            "payload": {"step": "start", "step_type": "notify"},
        },
        {
            "run_id": "run-1",
            "event_type": RuntimeEventType.STEP_ERROR,
            "payload": {
                "step": "start",
                "step_type": "notify",
                "error": "notify failed",
            },
        },
        {
            "run_id": "run-1",
            "event_type": RuntimeEventType.RUN_FINISHED,
            "payload": {
                "status": "FAILED",
                "error": "notify failed",
            },
        },
    ]


def test_worker_fails_when_step_type_is_not_supported() -> None:
    service, complete_run_use_case, fail_run_use_case = _build_service(
        render_results=[
            RenderCurrentStepResult(
                status=CurrentStepStatus.READY,
                current_step=_build_current_step(_UnknownStepType("custom")),
            )
        ],
    )

    result = service.run("run-1")

    assert result.status == RunWorkerStatus.FAILED
    assert result.error is not None
    assert "Unsupported step type 'custom' in step 'start'" in result.error
    assert complete_run_use_case.calls == []
    assert fail_run_use_case.calls == [{"run_id": "run-1", "error": result.error}]


def test_worker_fails_when_mcp_config_is_invalid() -> None:
    service, complete_run_use_case, fail_run_use_case = _build_service(
        render_results=[
            RenderCurrentStepResult(
                status=CurrentStepStatus.READY,
                current_step=_build_current_step(StepType.MCP),
            )
        ],
        mcp_render_result=_FakeRenderMcpConfigResult(
            status=RenderMcpConfigStatus.INVALID_CONFIG,
            error="missing transport",
        ),
    )

    result = service.run("run-1")

    assert result.status == RunWorkerStatus.FAILED
    assert result.error == "missing transport"
    assert complete_run_use_case.calls == []
    assert fail_run_use_case.calls == [{"run_id": "run-1", "error": "missing transport"}]
