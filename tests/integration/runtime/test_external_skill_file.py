from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from skiller.application.run_worker_service import RunWorkerService
from skiller.application.runtime_application_service import RuntimeApplicationService
from skiller.application.use_cases.bootstrap_runtime import BootstrapRuntimeUseCase
from skiller.application.use_cases.complete_run import CompleteRunUseCase
from skiller.application.use_cases.create_run import CreateRunUseCase
from skiller.application.use_cases.execute_assign_step import ExecuteAssignStepUseCase
from skiller.application.use_cases.execute_llm_prompt_step import ExecuteLlmPromptStepUseCase
from skiller.application.use_cases.execute_mcp_step import ExecuteMcpStepUseCase
from skiller.application.use_cases.execute_notify_step import ExecuteNotifyStepUseCase
from skiller.application.use_cases.execute_switch_step import ExecuteSwitchStepUseCase
from skiller.application.use_cases.execute_wait_input_step import ExecuteWaitInputStepUseCase
from skiller.application.use_cases.execute_wait_webhook_step import ExecuteWaitWebhookStepUseCase
from skiller.application.use_cases.execute_when_step import ExecuteWhenStepUseCase
from skiller.application.use_cases.fail_run import FailRunUseCase
from skiller.application.use_cases.get_run_status import GetRunStatusUseCase
from skiller.application.use_cases.get_start_step import GetStartStepUseCase
from skiller.application.use_cases.handle_input import HandleInputUseCase
from skiller.application.use_cases.handle_webhook import HandleWebhookUseCase
from skiller.application.use_cases.register_webhook import RegisterWebhookUseCase
from skiller.application.use_cases.remove_webhook import RemoveWebhookUseCase
from skiller.application.use_cases.render_current_step import (
    CurrentStepStatus,
    RenderCurrentStepUseCase,
)
from skiller.application.use_cases.render_mcp_config import RenderMcpConfigUseCase
from skiller.application.use_cases.resume_run import ResumeRunUseCase
from skiller.infrastructure.db.sqlite_state_store import SqliteStateStore
from skiller.infrastructure.db.sqlite_webhook_registry import SqliteWebhookRegistry
from skiller.infrastructure.llm.null_llm import NullLLM
from skiller.infrastructure.skills.filesystem_skill_runner import FilesystemSkillRunner
from skiller.infrastructure.tools.mcp.default_mcp import DefaultMCP

pytestmark = [
    pytest.mark.integration,
]


def _build_runtime(store: SqliteStateStore) -> RuntimeApplicationService:
    skill_runner = FilesystemSkillRunner(skills_dir="skills")
    webhook_registry = SqliteWebhookRegistry(store.db_path)
    mcp = DefaultMCP()
    fail_run_use_case = FailRunUseCase(store)
    complete_run_use_case = CompleteRunUseCase(store)
    render_current_step_use_case = RenderCurrentStepUseCase(store=store, skill_runner=skill_runner)
    render_mcp_config_use_case = RenderMcpConfigUseCase(store=store, skill_runner=skill_runner)
    execute_assign_step_use_case = ExecuteAssignStepUseCase(store=store)
    execute_llm_prompt_step_use_case = ExecuteLlmPromptStepUseCase(store=store, llm=NullLLM())
    execute_mcp_step_use_case = ExecuteMcpStepUseCase(store=store, mcp=mcp)
    execute_notify_step_use_case = ExecuteNotifyStepUseCase(store=store)
    execute_switch_step_use_case = ExecuteSwitchStepUseCase(store=store)
    execute_when_step_use_case = ExecuteWhenStepUseCase(store=store)
    execute_wait_input_step_use_case = ExecuteWaitInputStepUseCase(store=store)
    execute_wait_webhook_step_use_case = ExecuteWaitWebhookStepUseCase(store=store)
    run_worker_service = RunWorkerService(
        complete_run_use_case=complete_run_use_case,
        fail_run_use_case=fail_run_use_case,
        render_current_step_use_case=render_current_step_use_case,
        render_mcp_config_use_case=render_mcp_config_use_case,
        execute_assign_step_use_case=execute_assign_step_use_case,
        execute_llm_prompt_step_use_case=execute_llm_prompt_step_use_case,
        execute_mcp_step_use_case=execute_mcp_step_use_case,
        execute_notify_step_use_case=execute_notify_step_use_case,
        execute_switch_step_use_case=execute_switch_step_use_case,
        execute_when_step_use_case=execute_when_step_use_case,
        execute_wait_input_step_use_case=execute_wait_input_step_use_case,
        execute_wait_webhook_step_use_case=execute_wait_webhook_step_use_case,
    )

    runtime = RuntimeApplicationService(
        bootstrap_runtime_use_case=BootstrapRuntimeUseCase(store),
        create_run_use_case=CreateRunUseCase(store, skill_runner),
        fail_run_use_case=fail_run_use_case,
        get_start_step_use_case=GetStartStepUseCase(store=store),
        handle_input_use_case=HandleInputUseCase(store=store),
        handle_webhook_use_case=HandleWebhookUseCase(store=store),
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
                "inputs: {}\n"
                "steps:\n"
                "  - id: start\n"
                "    type: notify\n"
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
        notify_event = next(event for event in events if event["type"] == "NOTIFY")
        assert notify_event["payload"]["message"] == "external ok"


def test_external_skill_file_is_snapshotted_at_run_creation() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        skill_path = Path(tmpdir) / "external_notify.yaml"
        skill_path.write_text(
            (
                "name: external_notify\n"
                "inputs: {}\n"
                "steps:\n"
                "  - id: start\n"
                "    type: notify\n"
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
                "inputs: {}\n"
                "steps:\n"
                "  - id: start\n"
                "    type: notify\n"
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
                "inputs:\n"
                "  pr: string\n"
                "steps:\n"
                "  - id: start\n"
                "    type: wait_webhook\n"
                "    webhook: github-pr-merged\n"
                '    key: "{{inputs.pr}}"\n'
                "    next: done\n"
                "  - id: done\n"
                "    type: notify\n"
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
            event for event in store.list_events(run_id) if event["type"] == "WAITING"
        )
        assert wait_event["payload"]["webhook"] == "github-pr-merged"
        assert wait_event["payload"]["key"] == "42"

        resume_result = runtime.resume_run(run_id)
        resumed_run = store.get_run(run_id)

        assert resume_result["resume_status"] == "RESUMED"
        assert resume_result["status"] == "WAITING"
        assert resumed_run is not None
        assert resumed_run.status == "WAITING"

        events = store.list_events(run_id)
        assert any(event["type"] == "RUN_RESUMED" for event in events)
        assert not any(event["type"] == "NOTIFY" for event in events)


def test_external_wait_webhook_file_can_resume_from_webhook() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        skill_path = Path(tmpdir) / "external_wait.yaml"
        skill_path.write_text(
            (
                "name: external_wait\n"
                "inputs:\n"
                "  pr: string\n"
                "steps:\n"
                "  - id: start\n"
                "    type: wait_webhook\n"
                "    webhook: github-pr-merged\n"
                '    key: "{{inputs.pr}}"\n'
                "    next: done\n"
                "  - id: done\n"
                "    type: notify\n"
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
        wait_resolved = next(event for event in events if event["type"] == "WAIT_RESOLVED")
        assert wait_resolved["payload"]["step"] == "start"
        assert wait_resolved["payload"]["webhook"] == "github-pr-merged"
        assert wait_resolved["payload"]["key"] == "42"
        notify_event = next(event for event in events if event["type"] == "NOTIFY")
        assert notify_event["payload"]["message"] == "resumed from webhook"


def test_external_wait_input_file_can_resume_from_cli_input() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        skill_path = Path(tmpdir) / "external_wait_input.yaml"
        skill_path.write_text(
            (
                "name: external_wait_input\n"
                "inputs: {}\n"
                "steps:\n"
                "  - id: start\n"
                "    type: wait_input\n"
                "    prompt: Write a short summary\n"
                "    next: done\n"
                "  - id: done\n"
                "    type: notify\n"
                '    message: "{{results.start.payload.text}}"\n'
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
        assert resumed_run.context.results["start"] == {
            "ok": True,
            "prompt": "Write a short summary",
            "payload": {"text": "database timeout"},
        }

        events = store.list_events(run_id)
        input_resolved = next(event for event in events if event["type"] == "INPUT_RESOLVED")
        assert input_resolved["payload"]["step"] == "start"
        assert input_resolved["payload"]["prompt"] == "Write a short summary"
        notify_event = next(event for event in events if event["type"] == "NOTIFY")
        assert notify_event["payload"]["message"] == "database timeout"
