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
from skiller.application.use_cases.execute_switch_step import ExecuteSwitchStepUseCase
from skiller.application.use_cases.execute_wait_webhook_step import ExecuteWaitWebhookStepUseCase
from skiller.application.use_cases.execute_when_step import ExecuteWhenStepUseCase
from skiller.application.use_cases.fail_run import FailRunUseCase
from skiller.application.use_cases.get_run_status import GetRunStatusUseCase
from skiller.application.use_cases.get_start_step import GetStartStepUseCase
from skiller.application.use_cases.handle_webhook import HandleWebhookUseCase
from skiller.application.use_cases.list_webhooks import ListWebhooksUseCase
from skiller.application.use_cases.register_webhook import RegisterWebhookUseCase
from skiller.application.use_cases.remove_webhook import RemoveWebhookUseCase
from skiller.application.use_cases.render_current_step import RenderCurrentStepUseCase
from skiller.application.use_cases.render_mcp_config import RenderMcpConfigUseCase
from skiller.application.use_cases.resume_run import ResumeRunUseCase
from skiller.di.container import build_runtime_container
from skiller.infrastructure.config.settings import Settings
from skiller.infrastructure.db.sqlite_state_store import SqliteStateStore
from skiller.infrastructure.db.sqlite_webhook_registry import SqliteWebhookRegistry
from skiller.infrastructure.llm.fake_llm import FakeLLM
from skiller.infrastructure.skills.filesystem_skill_runner import FilesystemSkillRunner
from skiller.infrastructure.tools.mcp.default_mcp import DefaultMCP

pytestmark = [
    pytest.mark.integration,
]


class _FakeLLM:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate(
        self, messages: list[dict[str, str]], config: dict[str, object] | None = None
    ) -> dict[str, object]:
        self.calls.append({"messages": messages, "config": config})
        return {
            "ok": True,
            "content": (
                '{"summary":"tests failing on auth",'
                '"severity":"high","next_action":"retry"}'
            ),
            "model": "fake-llm",
        }


def _build_runtime(store: SqliteStateStore, llm: _FakeLLM) -> RuntimeApplicationService:
    skill_runner = FilesystemSkillRunner(skills_dir="skills")
    webhook_registry = SqliteWebhookRegistry(store.db_path)
    mcp = DefaultMCP()
    fail_run_use_case = FailRunUseCase(store)
    append_runtime_event_use_case = AppendRuntimeEventUseCase(store)
    complete_run_use_case = CompleteRunUseCase(store)
    render_current_step_use_case = RenderCurrentStepUseCase(store=store, skill_runner=skill_runner)
    render_mcp_config_use_case = RenderMcpConfigUseCase(store=store, skill_runner=skill_runner)
    execute_assign_step_use_case = ExecuteAssignStepUseCase(store=store)
    execute_llm_prompt_step_use_case = ExecuteLlmPromptStepUseCase(store=store, llm=llm)
    execute_mcp_step_use_case = ExecuteMcpStepUseCase(store=store, mcp=mcp)
    execute_notify_step_use_case = ExecuteNotifyStepUseCase(store=store)
    execute_switch_step_use_case = ExecuteSwitchStepUseCase(store=store)
    execute_when_step_use_case = ExecuteWhenStepUseCase(store=store)
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
        execute_switch_step_use_case=execute_switch_step_use_case,
        execute_when_step_use_case=execute_when_step_use_case,
        execute_wait_webhook_step_use_case=execute_wait_webhook_step_use_case,
    )

    runtime = RuntimeApplicationService(
        bootstrap_runtime_use_case=BootstrapRuntimeUseCase(store),
        append_runtime_event_use_case=append_runtime_event_use_case,
        create_run_use_case=CreateRunUseCase(store, skill_runner),
        fail_run_use_case=fail_run_use_case,
        get_start_step_use_case=GetStartStepUseCase(store=store),
        handle_webhook_use_case=HandleWebhookUseCase(store=store),
        list_webhooks_use_case=ListWebhooksUseCase(registry=webhook_registry),
        register_webhook_use_case=RegisterWebhookUseCase(registry=webhook_registry),
        remove_webhook_use_case=RemoveWebhookUseCase(registry=webhook_registry),
        resume_run_use_case=ResumeRunUseCase(store=store),
        get_run_status_use_case=GetRunStatusUseCase(store),
        run_worker_service=run_worker_service,
    )
    return runtime


def test_llm_prompt_step_succeeds_and_persists_json_result() -> None:
    llm = _FakeLLM()

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        skill_path = Path(tmpdir) / "llm_prompt.yaml"
        skill_path.write_text(
            (
                "name: llm_prompt_demo\n"
                "inputs:\n"
                "  stderr: string\n"
                "steps:\n"
                "  - id: start\n"
                "    type: llm_prompt\n"
                "    system: |\n"
                "      Eres un analista tecnico.\n"
                "      Responde solo JSON.\n"
                "    prompt: |\n"
                "      Analiza este error:\n"
                "      {{inputs.stderr}}\n"
                "    output:\n"
                "      format: json\n"
                "      schema:\n"
                "        type: object\n"
                "        required: [summary, severity, next_action]\n"
                "        properties:\n"
                "          summary:\n"
                "            type: string\n"
                "          severity:\n"
                "            type: string\n"
                "            enum: [low, medium, high]\n"
                "          next_action:\n"
                "            type: string\n"
                "            enum: [retry, ask_human, fail]\n"
                "    next: done\n"
                "  - id: done\n"
                "    type: notify\n"
                '    message: "{{results.start.next_action}}"\n'
            ),
            encoding="utf-8",
        )

        store = SqliteStateStore(db_path)
        store.init_db()
        runtime = _build_runtime(store, llm)

        run_result = runtime.run(
            str(skill_path), {"stderr": "Traceback auth failed"}, skill_source="file"
        )

        run = store.get_run(run_result["run_id"])
        assert run_result["status"] == "SUCCEEDED"
        assert run is not None
        assert run.status == "SUCCEEDED"
        assert run.context.results["start"] == {
            "summary": "tests failing on auth",
            "severity": "high",
            "next_action": "retry",
        }

        events = store.list_events(run_result["run_id"])
        llm_event = next(
            event
            for event in events
            if event["type"] == "STEP_SUCCESS" and event["payload"]["step"] == "start"
        )
        notify_event = next(
            event
            for event in events
            if event["type"] == "STEP_SUCCESS" and event["payload"]["step"] == "done"
        )

        assert llm_event["payload"]["result"]["json"]["severity"] == "high"
        assert notify_event["payload"]["result"]["message"] == "retry"
        assert llm.calls[0]["messages"][1]["content"].endswith("Traceback auth failed\n")


def test_llm_prompt_step_succeeds_with_fake_llm_provider_from_container() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        skill_path = Path(tmpdir) / "llm_prompt.yaml"
        skill_path.write_text(
            (
                "name: llm_prompt_demo\n"
                "inputs:\n"
                "  stderr: string\n"
                "steps:\n"
                "  - id: start\n"
                "    type: llm_prompt\n"
                "    system: Return JSON only.\n"
                "    prompt: '{{inputs.stderr}}'\n"
                "    output:\n"
                "      format: json\n"
                "      schema:\n"
                "        type: object\n"
                "        required: [summary, severity, next_action]\n"
                "        properties:\n"
                "          summary:\n"
                "            type: string\n"
                "          severity:\n"
                "            type: string\n"
                "            enum: [low, medium, high]\n"
                "          next_action:\n"
                "            type: string\n"
                "            enum: [retry, ask_human, fail]\n"
                "    next: done\n"
                "  - id: done\n"
                "    type: notify\n"
                "    message: '{{results.start.next_action}}'\n"
            ),
            encoding="utf-8",
        )

        container = build_runtime_container(
            Settings(
                db_path=db_path,
                llm_provider="fake",
                fake_llm_response_json=(
                    '{"summary":"container fake","severity":"medium","next_action":"ask_human"}'
                ),
                fake_llm_model="fake-llm-integration",
            ),
            skills_dir=tmpdir,
        )
        container.runtime_service.initialize()
        assert isinstance(
            container.runtime_service.run_worker_service.execute_llm_prompt_step_use_case.llm,
            FakeLLM,
        )

        run_result = container.runtime_service.run("llm_prompt", {"stderr": "boom"})
        run = container.query_service.get_run_status_use_case.execute(run_result["run_id"])

        assert run_result["status"] == "SUCCEEDED"
        assert run is not None
        assert run.context.results["start"] == {
            "summary": "container fake",
            "severity": "medium",
            "next_action": "ask_human",
        }

        events = container.query_service.get_run_logs_use_case.execute(run_result["run_id"])
        llm_event = next(
            event
            for event in events
            if event["type"] == "STEP_SUCCESS" and event["payload"]["step"] == "start"
        )
        notify_event = next(
            event
            for event in events
            if event["type"] == "STEP_SUCCESS" and event["payload"]["step"] == "done"
        )

        assert llm_event["payload"]["result"]["model"] == "fake-llm-integration"
        assert notify_event["payload"]["result"]["message"] == "ask_human"


def test_llm_prompt_failure_persists_step_error_and_run_finished() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        skill_path = Path(tmpdir) / "llm_prompt.yaml"
        skill_path.write_text(
            (
                "name: llm_prompt_demo\n"
                "inputs:\n"
                "  issue: string\n"
                "steps:\n"
                "  - id: start\n"
                "    type: llm_prompt\n"
                "    prompt: '{{inputs.issue}}'\n"
                "    output:\n"
                "      format: json\n"
                "      schema:\n"
                "        type: object\n"
                "        required: [summary]\n"
                "        properties:\n"
                "          summary:\n"
                "            type: string\n"
            ),
            encoding="utf-8",
        )

        container = build_runtime_container(
            Settings(
                db_path=db_path,
                llm_provider="fake",
                fake_llm_response_json="not-json",
                fake_llm_model="fake-llm-integration",
            ),
            skills_dir=tmpdir,
        )
        container.runtime_service.initialize()

        run_result = container.runtime_service.run("llm_prompt", {"issue": "boom"})
        run = container.query_service.get_run_status_use_case.execute(run_result["run_id"])
        events = container.query_service.get_run_logs_use_case.execute(run_result["run_id"])
        llm_error_event = next(event for event in events if event["type"] == "STEP_ERROR")
        failed_event = next(event for event in events if event["type"] == "RUN_FINISHED")

        assert run_result["status"] == "FAILED"
        assert run is not None
        assert run.status == "FAILED"
        assert llm_error_event["payload"] == {
            "step": "start",
            "step_type": "llm_prompt",
            "error": "LLM step 'start' returned invalid JSON: Expecting value",
        }
        assert failed_event["payload"] == {
            "status": "FAILED",
            "error": "LLM step 'start' returned invalid JSON: Expecting value",
        }


def test_llm_prompt_step_accepts_markdown_fenced_json_from_provider() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        skill_path = Path(tmpdir) / "llm_prompt.yaml"
        skill_path.write_text(
            (
                "name: llm_prompt_demo\n"
                "inputs:\n"
                "  issue: string\n"
                "steps:\n"
                "  - id: start\n"
                "    type: llm_prompt\n"
                "    prompt: '{{inputs.issue}}'\n"
                "    output:\n"
                "      format: json\n"
                "      schema:\n"
                "        type: object\n"
                "        required: [summary, severity, next_action]\n"
                "        properties:\n"
                "          summary:\n"
                "            type: string\n"
                "          severity:\n"
                "            type: string\n"
                "            enum: [low]\n"
                "          next_action:\n"
                "            type: string\n"
                "            enum: [retry]\n"
                "    next: done\n"
                "  - id: done\n"
                "    type: notify\n"
                "    message: '{{results.start.next_action}}'\n"
            ),
            encoding="utf-8",
        )

        container = build_runtime_container(
            Settings(
                db_path=db_path,
                llm_provider="fake",
                fake_llm_response_json='```json\n{"summary":"ok","severity":"low","next_action":"retry"}\n```',
                fake_llm_model="fake-llm-integration",
            ),
            skills_dir=tmpdir,
        )
        container.runtime_service.initialize()

        run_result = container.runtime_service.run("llm_prompt", {"issue": "boom"})
        run = container.query_service.get_run_status_use_case.execute(run_result["run_id"])
        events = container.query_service.get_run_logs_use_case.execute(run_result["run_id"])
        llm_event = next(
            event
            for event in events
            if event["type"] == "STEP_SUCCESS" and event["payload"]["step"] == "start"
        )

        assert run_result["status"] == "SUCCEEDED"
        assert run is not None
        assert run.context.results["start"] == {
            "summary": "ok",
            "severity": "low",
            "next_action": "retry",
        }
        assert llm_event["payload"]["result"]["json"]["next_action"] == "retry"
