from dataclasses import dataclass

import pytest

from skiller.application.run_worker_service import RunWorkerService, RunWorkerStatus
from skiller.application.use_cases.render_current_step import (
    CurrentStep,
    CurrentStepStatus,
    RenderCurrentStepResult,
    StepType,
)
from skiller.application.use_cases.render_mcp_config import RenderMcpConfigStatus
from skiller.application.use_cases.step_execution_result import (
    StepExecutionResult,
    StepExecutionStatus,
)
from skiller.domain.run_context_model import RunContext

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


class _FakeStepUseCase:
    def __init__(
        self,
        results: list[StepExecutionResult] | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.results = list(results or [])
        self.error = error
        self.calls: list[CurrentStep] = []

    def execute(self, current_step: CurrentStep) -> StepExecutionResult:
        self.calls.append(current_step)
        if self.error is not None:
            raise self.error
        if not self.results:
            raise AssertionError("No step execution results left")
        return self.results.pop(0)


class _FakeMcpStepUseCase:
    def __init__(self, result: StepExecutionResult) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def execute(self, current_step: CurrentStep, mcp_config: object) -> StepExecutionResult:
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
        step={"id": step_id, "type": getattr(step_type, "value", str(step_type))},
        context=RunContext(inputs={}, results={}),
    )


def _build_service(
    *,
    render_results: list[RenderCurrentStepResult],
    notify_results: list[StepExecutionResult] | None = None,
    wait_results: list[StepExecutionResult] | None = None,
    mcp_render_result: _FakeRenderMcpConfigResult | None = None,
    notify_error: Exception | None = None,
) -> tuple[RunWorkerService, _FakeCompleteRunUseCase, _FakeFailRunUseCase]:
    complete_run_use_case = _FakeCompleteRunUseCase()
    fail_run_use_case = _FakeFailRunUseCase()
    service = RunWorkerService(
        complete_run_use_case=complete_run_use_case,
        fail_run_use_case=fail_run_use_case,
        render_current_step_use_case=_FakeRenderCurrentStepUseCase(render_results),
        render_mcp_config_use_case=_FakeRenderMcpConfigUseCase(mcp_render_result),
        execute_assign_step_use_case=_FakeStepUseCase(),
        execute_llm_prompt_step_use_case=_FakeStepUseCase(),
        execute_mcp_step_use_case=_FakeMcpStepUseCase(
            StepExecutionResult(status=StepExecutionStatus.COMPLETED)
        ),
        execute_notify_step_use_case=_FakeStepUseCase(notify_results, error=notify_error),
        execute_switch_step_use_case=_FakeStepUseCase(),
        execute_when_step_use_case=_FakeStepUseCase(),
        execute_wait_webhook_step_use_case=_FakeStepUseCase(wait_results),
    )
    return service, complete_run_use_case, fail_run_use_case


def test_worker_returns_run_not_found() -> None:
    service, complete_run_use_case, fail_run_use_case = _build_service(
        render_results=[RenderCurrentStepResult(status=CurrentStepStatus.RUN_NOT_FOUND)],
    )

    result = service.run("run-1")

    assert result.status == RunWorkerStatus.RUN_NOT_FOUND
    assert complete_run_use_case.calls == []
    assert fail_run_use_case.calls == []


def test_worker_completes_run_when_renderer_reports_done() -> None:
    service, complete_run_use_case, fail_run_use_case = _build_service(
        render_results=[RenderCurrentStepResult(status=CurrentStepStatus.DONE)],
    )

    result = service.run("run-1")

    assert result.status == RunWorkerStatus.SUCCEEDED
    assert complete_run_use_case.calls == ["run-1"]
    assert fail_run_use_case.calls == []


def test_worker_returns_waiting_when_wait_step_blocks() -> None:
    service, complete_run_use_case, fail_run_use_case = _build_service(
        render_results=[
            RenderCurrentStepResult(
                status=CurrentStepStatus.READY,
                current_step=_build_current_step(StepType.WAIT_WEBHOOK),
            )
        ],
        wait_results=[StepExecutionResult(status=StepExecutionStatus.WAITING)],
    )

    result = service.run("run-1")

    assert result.status == RunWorkerStatus.WAITING
    assert complete_run_use_case.calls == []
    assert fail_run_use_case.calls == []


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
            StepExecutionResult(status=StepExecutionStatus.NEXT, next_step_id="done"),
            StepExecutionResult(status=StepExecutionStatus.COMPLETED),
        ],
    )

    result = service.run("run-1")

    assert result.status == RunWorkerStatus.SUCCEEDED
    assert complete_run_use_case.calls == ["run-1"]
    assert fail_run_use_case.calls == []


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
