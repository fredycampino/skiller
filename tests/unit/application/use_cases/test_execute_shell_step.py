import pytest

from skiller.application.use_cases.execute_shell_step import ExecuteShellStepUseCase
from skiller.application.use_cases.render_current_step import CurrentStep, StepType
from skiller.application.use_cases.step_execution_result import StepExecutionStatus
from skiller.domain.large_result_truncator import LargeResultTruncator
from skiller.domain.run_context_model import RunContext
from skiller.domain.run_model import RunStatus
from skiller.domain.step_execution_model import ShellOutput

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


class _FakeShell:
    def __init__(
        self,
        *,
        result: dict[str, object] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result or {
            "ok": True,
            "exit_code": 0,
            "stdout": "hello\n",
            "stderr": "",
        }
        self.error = error
        self.calls: list[dict[str, object]] = []

    def run(
        self,
        *,
        command: str,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: int | float | None = None,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "command": command,
                "cwd": cwd,
                "env": env,
                "timeout": timeout,
            }
        )
        if self.error is not None:
            raise self.error
        return dict(self.result)


class _FakeExecutionOutputStore:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def store_execution_output(
        self,
        *,
        run_id: str,
        step_id: str,
        output_body: dict[str, object],
    ) -> str:
        self.calls.append(
            {
                "run_id": run_id,
                "step_id": step_id,
                "output_body": output_body,
            }
        )
        return "execution_output:1"

    def get_execution_output(self, body_ref: str) -> dict[str, object] | None:
        _ = body_ref
        return None


def _build_use_case(
    *,
    store: _FakeStore | None = None,
    shell: _FakeShell | None = None,
    execution_output_store: _FakeExecutionOutputStore | None = None,
) -> ExecuteShellStepUseCase:
    return ExecuteShellStepUseCase(
        store=store or _FakeStore(),
        execution_output_store=execution_output_store or _FakeExecutionOutputStore(),
        shell=shell or _FakeShell(),
        large_result_truncator=LargeResultTruncator(),
    )


def test_execute_shell_step_moves_current_to_explicit_next() -> None:
    store = _FakeStore()
    shell = _FakeShell()
    use_case = _build_use_case(store=store, shell=shell)
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
    assert shell.calls == [
        {
            "command": "printf hello",
            "cwd": ".",
            "env": {"FOO": "bar"},
            "timeout": 30,
        }
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
    shell = _FakeShell(
        result={
            "ok": False,
            "exit_code": 7,
            "stdout": "",
            "stderr": "boom\n",
        }
    )
    use_case = _build_use_case(shell=shell)
    context = RunContext(inputs={}, step_executions={})

    with pytest.raises(ValueError, match="failed with exit code 7"):
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
    shell = _FakeShell(
        result={
            "ok": False,
            "exit_code": 7,
            "stdout": "",
            "stderr": "boom\n",
        }
    )
    use_case = _build_use_case(store=store, shell=shell)
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


def test_execute_shell_step_persists_large_result_body_and_truncates_output_value() -> None:
    store = _FakeStore()
    execution_output_store = _FakeExecutionOutputStore()
    shell = _FakeShell(
        result={
            "ok": True,
            "exit_code": 0,
            "stdout": "x" * 400,
            "stderr": "",
        }
    )
    use_case = _build_use_case(
        store=store,
        shell=shell,
        execution_output_store=execution_output_store,
    )
    context = RunContext(inputs={}, step_executions={})

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="run_tests",
            step_type=StepType.SHELL,
            step={"command": "python -c 'print()'", "large_result": True},
            context=context,
        )
    )

    expected_stdout = LargeResultTruncator().truncate({"stdout": "x" * 400})["stdout"]
    assert result.execution is not None
    assert result.execution.output == ShellOutput(
        text=str(expected_stdout),
        ok=True,
        exit_code=0,
        stdout=str(expected_stdout),
        stderr="",
        body_ref="execution_output:1",
    )
    assert execution_output_store.calls == [
        {
            "run_id": "run-1",
            "step_id": "run_tests",
            "output_body": {
                "value": {
                    "ok": True,
                    "exit_code": 0,
                    "stdout": "x" * 400,
                    "stderr": "",
                }
            },
        }
    ]


def test_execute_shell_step_raises_clear_timeout_error() -> None:
    shell = _FakeShell(error=TimeoutError("Shell command timed out after 3s"))
    use_case = _build_use_case(shell=shell)

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
