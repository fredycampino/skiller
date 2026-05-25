import pytest

from skiller.application.tools.shell import ShellProcessTool
from skiller.application.tools.shell.config import ShellToolRuntimeConfig
from skiller.application.use_cases.execute.execute_shell_step import ExecuteShellStepUseCase
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import RunStatus
from skiller.domain.run.steering_model import SteeringItem, SteeringItemType, SteeringStepInterrupt
from skiller.domain.step.current_step_model import CurrentStep
from skiller.domain.step.step_execution_model import ShellOutput
from skiller.domain.step.step_execution_result_model import StepExecutionStatus
from skiller.domain.step.step_type import StepType
from skiller.domain.tool.tool_process_model import (
    ToolProcessHandle,
    ToolProcessOutput,
    ToolProcessRequest,
    ToolProcessWait,
    ToolProcessWaitResult,
    ToolProcessWaitStatus,
)

pytestmark = pytest.mark.unit


class _FakeStore:
    def __init__(self) -> None:
        self.updated: list[dict[str, object]] = []

    def update_run(self, run_id: str, *, status=None, current=None, context=None) -> None:  # noqa: ANN001
        self.updated.append(
            {
                "run_id": run_id,
                "status": status,
                "current": current,
                "context": context,
            }
        )


class _FakeProcessRunner:
    def __init__(
        self,
        *,
        output: ToolProcessOutput | None = None,
        wait_status: ToolProcessWaitStatus = ToolProcessWaitStatus.COMPLETED,
    ) -> None:
        self.output = output or ToolProcessOutput(
            exit_code=0,
            stdout="hello\n",
            stderr="",
        )
        self.wait_status = wait_status
        self.requests: list[ToolProcessRequest] = []
        self.terminated: list[ToolProcessHandle] = []
        self.interrupt_signal_seen = False

    def popen(self, request: ToolProcessRequest) -> ToolProcessHandle:
        self.requests.append(request)
        return ToolProcessHandle(id="process-1", pid=1234)

    def write(self, handle: ToolProcessHandle, payload: str) -> None:
        _ = handle, payload

    def poll(self, handle: ToolProcessHandle) -> int | None:
        _ = handle
        return self.output.exit_code

    def read(self, handle: ToolProcessHandle) -> ToolProcessOutput:
        _ = handle
        return self.output

    def terminate(self, handle: ToolProcessHandle) -> None:
        self.terminated.append(handle)

    def wait(
        self,
        request: ToolProcessWait,
    ) -> ToolProcessWaitResult:
        if request.interrupt is not None:
            self.interrupt_signal_seen = True
            if request.interrupt.signal.is_interrupted(request.interrupt.run_id):
                return ToolProcessWaitResult(
                    status=ToolProcessWaitStatus.INTERRUPTED,
                    output=None,
                )
        return ToolProcessWaitResult(
            status=self.wait_status,
            output=self.output if self.wait_status == ToolProcessWaitStatus.COMPLETED else None,
        )


class _FakeAgentSteeringStore:
    def __init__(self, *, interrupted: bool = False) -> None:
        self.interrupted = interrupted
        self.popped: list[tuple[str, SteeringItemType]] = []

    def append(self, run_id: str, item: SteeringItem) -> None:
        _ = run_id, item

    def pop(self, run_id: str, item_type: SteeringItemType) -> list[SteeringItem]:
        self.popped.append((run_id, item_type))
        if self.interrupted:
            return [SteeringStepInterrupt()]
        return []


def _build_use_case(
    *,
    store: _FakeStore | None = None,
    process_runner: _FakeProcessRunner | None = None,
    agent_steering_store: _FakeAgentSteeringStore | None = None,
) -> ExecuteShellStepUseCase:
    return ExecuteShellStepUseCase(
        store=store or _FakeStore(),
        shell_tool=ShellProcessTool(shell="/bin/bash"),
        shell_config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            workspace="/workspace",
        ),
        process_runner=process_runner or _FakeProcessRunner(),
        agent_steering_store=agent_steering_store or _FakeAgentSteeringStore(),
    )


def test_execute_shell_step_moves_current_to_explicit_next() -> None:
    store = _FakeStore()
    process_runner = _FakeProcessRunner()
    use_case = _build_use_case(store=store, process_runner=process_runner)
    context = RunContext(inputs={}, step_executions={})

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="run_tests",
            step_type=StepType.SHELL,
            step={
                "command": "printf hello",
                "cwd": ".",
                "env": {"FOO": "bar"},
                "timeout": 30,
                "check": True,
                "next": "done",
            },
            context=context,
        )
    )

    assert result.status == StepExecutionStatus.NEXT
    assert result.next_step_id == "done"
    assert result.execution is not None
    assert result.execution.output == ShellOutput(
        text="hello",
        ok=True,
        exit_code=0,
        stdout="hello\n",
        stderr="",
    )
    assert process_runner.requests == [
        ToolProcessRequest(
            command=["/bin/bash", "-lc", "printf hello"],
            cwd="/workspace",
            env={"FOO": "bar"},
            timeout=30,
        )
    ]
    assert context.step_executions["run_tests"] == result.execution
    assert store.updated == [
        {
            "run_id": "run-1",
            "status": RunStatus.RUNNING,
            "current": "done",
            "context": context,
        }
    ]


def test_execute_shell_step_marks_completed_when_next_is_missing() -> None:
    store = _FakeStore()
    use_case = _build_use_case(store=store)
    context = RunContext(inputs={}, step_executions={})

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="run_tests",
            step_type=StepType.SHELL,
            step={"command": "printf hello"},
            context=context,
        )
    )

    assert result.status == StepExecutionStatus.COMPLETED
    assert result.next_step_id is None
    assert result.execution is not None
    assert result.execution.output == ShellOutput(
        text="hello",
        ok=True,
        exit_code=0,
        stdout="hello\n",
        stderr="",
    )
    assert store.updated == [
        {
            "run_id": "run-1",
            "status": RunStatus.RUNNING,
            "current": None,
            "context": context,
        }
    ]


def test_execute_shell_step_raises_on_non_zero_exit_when_check_is_true() -> None:
    process_runner = _FakeProcessRunner(
        output=ToolProcessOutput(
            exit_code=7,
            stdout="",
            stderr="boom\n",
        )
    )
    use_case = _build_use_case(process_runner=process_runner)
    context = RunContext(inputs={}, step_executions={})

    with pytest.raises(ValueError, match="Shell step 'run_tests' failed: boom"):
        use_case.execute(
            CurrentStep(
                run_id="run-1",
                step_index=0,
                step_id="run_tests",
                step_type=StepType.SHELL,
                step={"command": "exit 7"},
                context=context,
            )
        )

    assert context.step_executions == {}


def test_execute_shell_step_keeps_legacy_non_zero_error_when_stderr_is_empty() -> None:
    process_runner = _FakeProcessRunner(
        output=ToolProcessOutput(
            exit_code=7,
            stdout="",
            stderr="",
        )
    )
    use_case = _build_use_case(process_runner=process_runner)
    context = RunContext(inputs={}, step_executions={})

    with pytest.raises(ValueError, match="Shell step 'run_tests' failed: $"):
        use_case.execute(
            CurrentStep(
                run_id="run-1",
                step_index=0,
                step_id="run_tests",
                step_type=StepType.SHELL,
                step={"command": "exit 7"},
                context=context,
            )
        )

    assert context.step_executions == {}


def test_execute_shell_step_keeps_non_zero_exit_in_output_when_check_is_false() -> None:
    store = _FakeStore()
    process_runner = _FakeProcessRunner(
        output=ToolProcessOutput(
            exit_code=7,
            stdout="",
            stderr="boom\n",
        )
    )
    use_case = _build_use_case(store=store, process_runner=process_runner)
    context = RunContext(inputs={}, step_executions={})

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="run_tests",
            step_type=StepType.SHELL,
            step={"command": "exit 7", "check": False},
            context=context,
        )
    )

    assert result.status == StepExecutionStatus.COMPLETED
    assert result.execution is not None
    assert result.execution.output == ShellOutput(
        text="boom",
        ok=False,
        exit_code=7,
        stdout="",
        stderr="boom\n",
    )


def test_execute_shell_step_raises_clear_timeout_error() -> None:
    process_runner = _FakeProcessRunner(wait_status=ToolProcessWaitStatus.TIMEOUT)
    use_case = _build_use_case(process_runner=process_runner)

    with pytest.raises(ValueError, match="timed out after 3s"):
        use_case.execute(
            CurrentStep(
                run_id="run-1",
                step_index=0,
                step_id="run_tests",
                step_type=StepType.SHELL,
                step={"command": "sleep 10", "timeout": 3},
                context=RunContext(inputs={}, step_executions={}),
            )
        )


def test_execute_shell_step_raises_policy_error_before_process_starts() -> None:
    process_runner = _FakeProcessRunner()
    use_case = _build_use_case(process_runner=process_runner)

    with pytest.raises(ValueError, match="shell command path escapes workspace"):
        use_case.execute(
            CurrentStep(
                run_id="run-1",
                step_index=0,
                step_id="run_tests",
                step_type=StepType.SHELL,
                step={"command": "cat /etc/passwd"},
                context=RunContext(inputs={}, step_executions={}),
            )
        )

    assert process_runner.requests == []


def test_execute_shell_step_pops_step_interrupt_while_waiting_for_process() -> None:
    agent_steering_store = _FakeAgentSteeringStore(interrupted=True)
    process_runner = _FakeProcessRunner()
    use_case = _build_use_case(
        process_runner=process_runner,
        agent_steering_store=agent_steering_store,
    )

    with pytest.raises(ValueError, match="was interrupted"):
        use_case.execute(
            CurrentStep(
                run_id="run-1",
                step_index=0,
                step_id="run_tests",
                step_type=StepType.SHELL,
                step={"command": "sleep 10"},
                context=RunContext(inputs={}, step_executions={}),
            )
        )

    assert process_runner.interrupt_signal_seen is True
    assert agent_steering_store.popped == [("run-1", SteeringStepInterrupt)]
