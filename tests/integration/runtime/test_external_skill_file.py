from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from skiller.application.run_worker_service import RunWorkerService
from skiller.application.runtime_application_service import RuntimeApplicationService
from skiller.application.use_cases.append_runtime_event import AppendRuntimeEventUseCase
from skiller.application.use_cases.bootstrap_runtime import BootstrapRuntimeUseCase
from skiller.application.use_cases.complete_run import CompleteRunUseCase
from skiller.application.use_cases.create_run import CreateRunUseCase
from skiller.application.use_cases.execute_assign_step import ExecuteAssignStepUseCase
from skiller.application.use_cases.execute_llm_prompt_step import ExecuteLlmPromptStepUseCase
from skiller.application.use_cases.execute_mcp_step import ExecuteMcpStepUseCase
from skiller.application.use_cases.execute_notify_step import ExecuteNotifyStepUseCase
from skiller.application.use_cases.execute_shell_step import ExecuteShellStepUseCase
from skiller.application.use_cases.execute_switch_step import ExecuteSwitchStepUseCase
from skiller.application.use_cases.execute_wait_input_step import ExecuteWaitInputStepUseCase
from skiller.application.use_cases.execute_wait_webhook_step import ExecuteWaitWebhookStepUseCase
from skiller.application.use_cases.execute_when_step import ExecuteWhenStepUseCase
from skiller.application.use_cases.fail_run import FailRunUseCase
from skiller.application.use_cases.get_run_status import GetRunStatusUseCase
from skiller.application.use_cases.get_start_step import GetStartStepUseCase
from skiller.application.use_cases.handle_input import HandleInputUseCase
from skiller.application.use_cases.handle_webhook import HandleWebhookUseCase
from skiller.application.use_cases.list_webhooks import ListWebhooksUseCase
from skiller.application.use_cases.register_webhook import RegisterWebhookUseCase
from skiller.application.use_cases.remove_webhook import RemoveWebhookUseCase
from skiller.application.use_cases.render_current_step import (
    CurrentStepStatus,
    RenderCurrentStepUseCase,
)
from skiller.application.use_cases.render_mcp_config import RenderMcpConfigUseCase
from skiller.application.use_cases.resume_run import ResumeRunUseCase
from skiller.domain.large_result_truncator import LargeResultTruncator
from skiller.infrastructure.db.sqlite_execution_output_store import SqliteExecutionOutputStore
from skiller.infrastructure.db.sqlite_state_store import SqliteStateStore
from skiller.infrastructure.db.sqlite_webhook_registry import SqliteWebhookRegistry
from skiller.infrastructure.llm.null_llm import NullLLM
from skiller.infrastructure.skills.filesystem_skill_runner import FilesystemSkillRunner
from skiller.infrastructure.tools.mcp.default_mcp import DefaultMCP
from skiller.infrastructure.tools.shell.default_shell import DefaultShellRunner

pytestmark = [
    pytest.mark.integration,
]


def _build_runtime(store: SqliteStateStore) -> RuntimeApplicationService:
    skill_runner = FilesystemSkillRunner(skills_dir="skills")
    execution_output_store = SqliteExecutionOutputStore(store.db_path)
    execution_output_store.init_db()
    webhook_registry = SqliteWebhookRegistry(store.db_path)
    mcp = DefaultMCP()
    shell = DefaultShellRunner()
    fail_run_use_case = FailRunUseCase(store)
    append_runtime_event_use_case = AppendRuntimeEventUseCase(store)
    complete_run_use_case = CompleteRunUseCase(store)
    render_current_step_use_case = RenderCurrentStepUseCase(store=store, skill_runner=skill_runner)
    render_mcp_config_use_case = RenderMcpConfigUseCase(store=store, skill_runner=skill_runner)
    execute_assign_step_use_case = ExecuteAssignStepUseCase(store=store)
    execute_llm_prompt_step_use_case = ExecuteLlmPromptStepUseCase(
        store=store,
        execution_output_store=execution_output_store,
        llm=NullLLM(),
        large_result_truncator=LargeResultTruncator(),
    )
    execute_mcp_step_use_case = ExecuteMcpStepUseCase(
        store=store,
        execution_output_store=execution_output_store,
        mcp=mcp,
        large_result_truncator=LargeResultTruncator(),
    )
    execute_notify_step_use_case = ExecuteNotifyStepUseCase(store=store)
    execute_shell_step_use_case = ExecuteShellStepUseCase(
        store=store,
        execution_output_store=execution_output_store,
        shell=shell,
        large_result_truncator=LargeResultTruncator(),
    )
    execute_switch_step_use_case = ExecuteSwitchStepUseCase(store=store)
    execute_when_step_use_case = ExecuteWhenStepUseCase(store=store)
    execute_wait_input_step_use_case = ExecuteWaitInputStepUseCase(store=store)
    execute_wait_webhook_step_use_case = ExecuteWaitWebhookStepUseCase(store=store)
    run_worker_service = RunWorkerService(
        complete_run_use_case=complete_run_use_case,
        fail_run_use_case=fail_run_use_case,
        append_runtime_event_use_case=append_runtime_event_use_case,
        render_current_step_use_case=render_current_step_use_case,
        render_mcp_config_use_case=render_mcp_config_use_case,
        execute_assign_step_use_case=execute_assign_step_use_case,
        execute_llm_prompt_step_use_case=execute_llm_prompt_step_use_case,
        execute_mcp_step_use_case=execute_mcp_step_use_case,
        execute_notify_step_use_case=execute_notify_step_use_case,
        execute_shell_step_use_case=execute_shell_step_use_case,
        execute_switch_step_use_case=execute_switch_step_use_case,
        execute_when_step_use_case=execute_when_step_use_case,
        execute_wait_input_step_use_case=execute_wait_input_step_use_case,
        execute_wait_webhook_step_use_case=execute_wait_webhook_step_use_case,
    )

    runtime = RuntimeApplicationService(
        bootstrap_runtime_use_case=BootstrapRuntimeUseCase(
            store=store,
            execution_output_store=execution_output_store,
            webhook_registry=webhook_registry,
        ),
        append_runtime_event_use_case=append_runtime_event_use_case,
        create_run_use_case=CreateRunUseCase(store, skill_runner),
        fail_run_use_case=fail_run_use_case,
        get_start_step_use_case=GetStartStepUseCase(store=store),
        handle_input_use_case=HandleInputUseCase(store=store),
        handle_webhook_use_case=HandleWebhookUseCase(store=store),
        list_webhooks_use_case=ListWebhooksUseCase(registry=webhook_registry),
        register_webhook_use_case=RegisterWebhookUseCase(registry=webhook_registry),
        remove_webhook_use_case=RemoveWebhookUseCase(registry=webhook_registry),
        resume_run_use_case=ResumeRunUseCase(store=store),
        get_run_status_use_case=GetRunStatusUseCase(store),
        run_worker_service=run_worker_service,
    )
    return runtime


def test_run_external_skill_file_succeeds() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        skill_path = Path(tmpdir) / "external_notify.yaml"
        skill_path.write_text(
            (
                "name: external_notify\n"
                "start: show_message\n"
                "inputs: {}\n"
                "steps:\n"
                "  - notify: show_message\n"
                "    message: external ok\n"
            ),
            encoding="utf-8",
        )

        store = SqliteStateStore(db_path)
        store.init_db()
        runtime = _build_runtime(store)

        run_result = runtime.run(str(skill_path), {}, skill_source="file")

        run = store.get_run(run_result["run_id"])
        assert run_result["status"] == "SUCCEEDED"
        assert run is not None
        assert run.skill_source == "file"
        assert run.skill_ref == str(skill_path)
        assert run.skill_snapshot["name"] == "external_notify"
        events = store.list_events(run_result["run_id"])
        notify_event = next(
            event
            for event in events
            if event["type"] == "STEP_SUCCESS" and event["payload"]["step"] == "show_message"
        )
        assert notify_event["payload"]["output"]["value"]["message"] == "external ok"


def test_external_shell_step_persists_large_result_body() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        skill_path = Path(tmpdir) / "external_shell.yaml"
        skill_path.write_text(
            (
                "name: external_shell\n"
                "start: run_command\n"
                "inputs: {}\n"
                "steps:\n"
                "  - shell: run_command\n"
                "    command: python3 -c \"print('x' * 400)\"\n"
                "    large_result: true\n"
            ),
            encoding="utf-8",
        )

        store = SqliteStateStore(db_path)
        store.init_db()
        runtime = _build_runtime(store)

        run_result = runtime.run(str(skill_path), {}, skill_source="file")

        run = store.get_run(run_result["run_id"])
        assert run_result["status"] == "SUCCEEDED"
        assert run is not None
        output = run.context.step_executions["run_command"].output.to_public_dict()
        body_ref = output["body_ref"]
        assert isinstance(body_ref, str)
        assert body_ref.startswith("execution_output:")
        assert output == {
            "text": ("x" * 197) + "...",
            "value": {
                "ok": True,
                "exit_code": 0,
                "stdout": ("x" * 197) + "...",
                "stderr": "",
            },
            "body_ref": body_ref,
        }

        execution_output_store = SqliteExecutionOutputStore(db_path)
        execution_output_store.init_db()
        assert execution_output_store.get_execution_output(body_ref) == {
            "value": {
                "ok": True,
                "exit_code": 0,
                "stdout": ("x" * 400) + "\n",
                "stderr": "",
            }
        }


def test_external_skill_file_is_snapshotted_at_run_creation() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        skill_path = Path(tmpdir) / "external_notify.yaml"
        skill_path.write_text(
            (
                "name: external_notify\n"
                "start: show_message\n"
                "inputs: {}\n"
                "steps:\n"
                "  - notify: show_message\n"
                "    message: original\n"
            ),
            encoding="utf-8",
        )

        store = SqliteStateStore(db_path)
        store.init_db()
        skill_runner = FilesystemSkillRunner(skills_dir="skills")
        create_run_use_case = CreateRunUseCase(store, skill_runner)
        get_start_step_use_case = GetStartStepUseCase(store=store)
        render_current_step_use_case = RenderCurrentStepUseCase(
            store=store, skill_runner=skill_runner
        )

        run_id = create_run_use_case.execute(str(skill_path), {}, skill_source="file")
        get_start_step_use_case.execute(run_id)

        skill_path.write_text(
            (
                "name: external_notify\n"
                "start: show_message\n"
                "inputs: {}\n"
                "steps:\n"
                "  - notify: show_message\n"
                "    message: mutated\n"
            ),
            encoding="utf-8",
        )

        run = store.get_run(run_id)
        result = render_current_step_use_case.execute(run_id)

        assert run is not None
        assert run.skill_snapshot["steps"][0]["message"] == "original"
        assert result.status == CurrentStepStatus.READY
        assert result.current_step is not None
        assert result.current_step.step["message"] == "original"


def test_external_wait_webhook_file_can_resume_manually() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        skill_path = Path(tmpdir) / "external_wait.yaml"
        skill_path.write_text(
            (
                "name: external_wait\n"
                "start: wait_merge\n"
                "inputs:\n"
                "  pr: string\n"
                "steps:\n"
                "  - wait_webhook: wait_merge\n"
                "    webhook: github-pr-merged\n"
                '    key: "{{inputs.pr}}"\n'
                "    next: done\n"
                "  - notify: done\n"
                "    message: resumed ok\n"
            ),
            encoding="utf-8",
        )

        store = SqliteStateStore(db_path)
        store.init_db()
        runtime = _build_runtime(store)

        run_result = runtime.run(str(skill_path), {"pr": "42"}, skill_source="file")
        run_id = run_result["run_id"]
        run = store.get_run(run_id)

        assert run_result["status"] == "WAITING"
        assert run is not None
        assert run.status == "WAITING"

        wait_event = next(
            event
            for event in store.list_events(run_id)
            if event["type"] == "RUN_WAITING"
        )
        assert wait_event["payload"]["output"]["value"]["webhook"] == "github-pr-merged"
        assert wait_event["payload"]["output"]["value"]["key"] == "42"

        resume_result = runtime.resume_run(run_id)
        resumed_run = store.get_run(run_id)

        assert resume_result["resume_status"] == "RESUMED"
        assert resume_result["status"] == "WAITING"
        assert resumed_run is not None
        assert resumed_run.status == "WAITING"

        events = store.list_events(run_id)
        assert any(event["type"] == "RUN_RESUME" for event in events)
        assert not any(
            event["type"] == "STEP_SUCCESS" and event["payload"]["step_type"] == "notify"
            for event in events
        )


def test_external_wait_webhook_file_can_resume_from_webhook() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        skill_path = Path(tmpdir) / "external_wait.yaml"
        skill_path.write_text(
            (
                "name: external_wait\n"
                "start: wait_merge\n"
                "inputs:\n"
                "  pr: string\n"
                "steps:\n"
                "  - wait_webhook: wait_merge\n"
                "    webhook: github-pr-merged\n"
                '    key: "{{inputs.pr}}"\n'
                "    next: done\n"
                "  - notify: done\n"
                "    message: resumed from webhook\n"
            ),
            encoding="utf-8",
        )

        store = SqliteStateStore(db_path)
        store.init_db()
        runtime = _build_runtime(store)

        run_result = runtime.run(str(skill_path), {"pr": "42"}, skill_source="file")
        run_id = run_result["run_id"]

        assert run_result["status"] == "WAITING"

        matched_runs = runtime.handle_webhook(
            "github-pr-merged", "42", {"merged": True}, dedup_key="dedup-1"
        )
        matched_run = store.get_run(run_id)

        assert matched_runs["accepted"] is True
        assert matched_runs["duplicate"] is False
        assert matched_runs["matched_runs"] == [run_id]
        assert matched_run is not None
        assert matched_run.status == "WAITING"

        resume_result = runtime.resume_run(run_id)
        resumed_run = store.get_run(run_id)

        assert resume_result["resume_status"] == "RESUMED"
        assert resume_result["status"] == "SUCCEEDED"
        assert resumed_run is not None
        assert resumed_run.status == "SUCCEEDED"

        events = store.list_events(run_id)
        wait_resolved = next(
            event
            for event in events
            if event["type"] == "STEP_SUCCESS" and event["payload"]["step"] == "wait_merge"
        )
        assert wait_resolved["payload"]["output"] == {
            "text": "Webhook received: github-pr-merged:42.",
            "value": {
                "webhook": "github-pr-merged",
                "key": "42",
                "payload": {"merged": True},
            },
            "body_ref": None,
        }
        notify_event = next(
            event
            for event in events
            if event["type"] == "STEP_SUCCESS" and event["payload"]["step"] == "done"
        )
        assert notify_event["payload"]["output"]["value"]["message"] == "resumed from webhook"


def test_external_wait_input_file_can_resume_from_cli_input() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        skill_path = Path(tmpdir) / "external_wait_input.yaml"
        skill_path.write_text(
            (
                "name: external_wait_input\n"
                "start: ask_user\n"
                "inputs: {}\n"
                "steps:\n"
                "  - wait_input: ask_user\n"
                "    prompt: Write a short summary\n"
                "    next: done\n"
                "  - notify: done\n"
                '    message: "{{step_executions.ask_user.output.value.payload.text}}"\n'
            ),
            encoding="utf-8",
        )

        store = SqliteStateStore(db_path)
        store.init_db()
        runtime = _build_runtime(store)

        run_result = runtime.run(str(skill_path), {}, skill_source="file")
        run_id = run_result["run_id"]

        assert run_result["status"] == "WAITING"

        input_result = runtime.handle_input(run_id, text="database timeout")
        waiting_run = store.get_run(run_id)

        assert input_result == {
            "accepted": True,
            "run_id": run_id,
            "matched_runs": [run_id],
        }
        assert waiting_run is not None
        assert waiting_run.status == "WAITING"

        resume_result = runtime.resume_run(run_id)
        resumed_run = store.get_run(run_id)

        assert resume_result["resume_status"] == "RESUMED"
        assert resume_result["status"] == "SUCCEEDED"
        assert resumed_run is not None
        assert resumed_run.status == "SUCCEEDED"
        assert (
            resumed_run.context.step_executions["ask_user"].input["prompt"]
            == "Write a short summary"
        )
        assert resumed_run.context.step_executions["ask_user"].output.to_public_dict()["value"] == {
            "prompt": "Write a short summary",
            "payload": {
                "text": "database timeout"
            },
        }
        assert resumed_run.context.step_executions["ask_user"].evaluation["input_event_id"]

        events = store.list_events(run_id)
        run_waiting_event = next(event for event in events if event["type"] == "RUN_WAITING")
        assert run_waiting_event["payload"]["step"] == "ask_user"
        assert run_waiting_event["payload"]["step_type"] == "wait_input"
        assert run_waiting_event["payload"]["output"]["value"]["prompt"] == "Write a short summary"

        step_success_event = next(
            event
            for event in events
            if event["type"] == "STEP_SUCCESS" and event["payload"]["step"] == "ask_user"
        )
        assert step_success_event["payload"]["output"] == {
            "text": "Input received.",
            "value": {
                "prompt": "Write a short summary",
                "payload": {"text": "database timeout"},
            },
            "body_ref": None,
        }

        notify_event = next(
            event
            for event in events
            if event["type"] == "STEP_SUCCESS" and event["payload"]["step"] == "done"
        )
        assert notify_event["payload"]["output"]["value"]["message"] == "database timeout"


def test_external_wait_input_loop_does_not_reconsume_previous_input() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        skill_path = Path(tmpdir) / "external_wait_input_loop.yaml"
        skill_path.write_text(
            (
                "name: external_wait_input_loop\n"
                "start: ask_user\n"
                "inputs: {}\n"
                "steps:\n"
                "  - wait_input: ask_user\n"
                "    prompt: Write a short summary\n"
                "    next: echo\n"
                "  - notify: echo\n"
                '    message: "{{step_executions.ask_user.output.value.payload.text}}"\n'
                "    next: ask_user\n"
            ),
            encoding="utf-8",
        )

        store = SqliteStateStore(db_path)
        store.init_db()
        runtime = _build_runtime(store)

        run_result = runtime.run(str(skill_path), {}, skill_source="file")
        run_id = run_result["run_id"]

        assert run_result["status"] == "WAITING"

        first_input = runtime.handle_input(run_id, text="first reply")
        first_resume = runtime.resume_run(run_id)
        run_after_first_resume = store.get_run(run_id)

        assert first_input == {
            "accepted": True,
            "run_id": run_id,
            "matched_runs": [run_id],
        }
        assert first_resume["resume_status"] == "RESUMED"
        assert first_resume["status"] == "WAITING"
        assert run_after_first_resume is not None
        assert run_after_first_resume.status == "WAITING"
        assert run_after_first_resume.current == "ask_user"
        assert (
            run_after_first_resume.context.step_executions["ask_user"]
            .output.to_public_dict()["value"]["payload"]
            == {"text": "first reply"}
        )

        second_input = runtime.handle_input(run_id, text="second reply")
        second_resume = runtime.resume_run(run_id)
        run_after_second_resume = store.get_run(run_id)

        assert second_input == {
            "accepted": True,
            "run_id": run_id,
            "matched_runs": [run_id],
        }
        assert second_resume["resume_status"] == "RESUMED"
        assert second_resume["status"] == "WAITING"
        assert run_after_second_resume is not None
        assert run_after_second_resume.status == "WAITING"
        assert run_after_second_resume.current == "ask_user"
        assert (
            run_after_second_resume.context.step_executions["ask_user"]
            .output.to_public_dict()["value"]["payload"]
            == {"text": "second reply"}
        )

        events = store.list_events(run_id)
        input_resolved_events = [
            event
            for event in events
            if event["type"] == "STEP_SUCCESS" and event["payload"]["step"] == "ask_user"
        ]
        notify_events = [
            event
            for event in events
            if event["type"] == "STEP_SUCCESS" and event["payload"]["step"] == "echo"
        ]
        input_waiting_events = [event for event in events if event["type"] == "RUN_WAITING"]

        assert len(input_resolved_events) == 2
        assert input_resolved_events[0]["payload"]["output"]["value"]["payload"] == {
            "text": "first reply"
        }
        assert input_resolved_events[1]["payload"]["output"]["value"]["payload"] == {
            "text": "second reply"
        }
        assert [event["payload"]["output"]["value"]["message"] for event in notify_events] == [
            "first reply",
            "second reply",
        ]
        assert len(input_waiting_events) == 3
