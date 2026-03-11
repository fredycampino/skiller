import tempfile
from pathlib import Path

import pytest

from skiller.application.runtime_application_service import RuntimeApplicationService
from skiller.application.use_cases.complete_run import CompleteRunUseCase
from skiller.application.use_cases.execute_assign_step import ExecuteAssignStepUseCase
from skiller.application.use_cases.execute_llm_prompt_step import ExecuteLlmPromptStepUseCase
from skiller.application.use_cases.execute_mcp_step import ExecuteMcpStepUseCase
from skiller.application.use_cases.execute_notify_step import ExecuteNotifyStepUseCase
from skiller.application.use_cases.execute_wait_webhook_step import ExecuteWaitWebhookStepUseCase
from skiller.application.use_cases.fail_run import FailRunUseCase
from skiller.application.use_cases.render_current_step import RenderCurrentStepUseCase
from skiller.application.use_cases.get_run_status import GetRunStatusUseCase
from skiller.application.use_cases.get_start_step import GetStartStepUseCase
from skiller.application.use_cases.handle_webhook import HandleWebhookUseCase
from skiller.application.use_cases.register_webhook import RegisterWebhookUseCase
from skiller.application.use_cases.render_mcp_config import RenderMcpConfigUseCase
from skiller.application.use_cases.remove_webhook import RemoveWebhookUseCase
from skiller.application.use_cases.resume_run import ResumeRunUseCase
from skiller.application.use_cases.start_run import StartRunUseCase
from skiller.infrastructure.db.sqlite_state_store import SqliteStateStore
from skiller.infrastructure.db.sqlite_webhook_registry import SqliteWebhookRegistry
from skiller.infrastructure.llm.null_llm import NullLLM
from skiller.infrastructure.skills.filesystem_skill_runner import FilesystemSkillRunner
from skiller.infrastructure.tools.mcp.default_mcp import DefaultMCP

pytestmark = pytest.mark.integration

def _build_runtime(store: SqliteStateStore) -> RuntimeApplicationService:
    skill_runner = FilesystemSkillRunner(skills_dir="skills")
    webhook_registry = SqliteWebhookRegistry(store.db_path)
    mcp = DefaultMCP()

    runtime = RuntimeApplicationService(
        start_run_use_case=StartRunUseCase(store, skill_runner),
        complete_run_use_case=CompleteRunUseCase(store),
        fail_run_use_case=FailRunUseCase(store),
        get_start_step_use_case=GetStartStepUseCase(store=store),
        render_current_step_use_case=RenderCurrentStepUseCase(store=store, skill_runner=skill_runner),
        render_mcp_config_use_case=RenderMcpConfigUseCase(store=store, skill_runner=skill_runner),
        execute_assign_step_use_case=ExecuteAssignStepUseCase(store=store),
        execute_llm_prompt_step_use_case=ExecuteLlmPromptStepUseCase(store=store, llm=NullLLM()),
        execute_mcp_step_use_case=ExecuteMcpStepUseCase(store=store, mcp=mcp),
        execute_notify_step_use_case=ExecuteNotifyStepUseCase(store=store),
        execute_wait_webhook_step_use_case=ExecuteWaitWebhookStepUseCase(store=store),
        handle_webhook_use_case=HandleWebhookUseCase(store=store),
        register_webhook_use_case=RegisterWebhookUseCase(registry=webhook_registry),
        remove_webhook_use_case=RemoveWebhookUseCase(registry=webhook_registry),
        resume_run_use_case=ResumeRunUseCase(store=store),
        get_run_status_use_case=GetRunStatusUseCase(store),
    )
    return runtime


@pytest.mark.parametrize(
    ("skill_ref", "inputs", "expected_event", "expected_step", "expected_tool", "expected_mcp"),
    [
        ("notify_test", {}, "NOTIFY", "start", None, None),
    ],
)
def test_basic_skill_examples_succeed(
    skill_ref: str,
    inputs: dict[str, str],
    expected_event: str,
    expected_step: str,
    expected_tool: str | None,
    expected_mcp: str | None,
) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        store = SqliteStateStore(db_path)
        store.init_db()

        runtime = _build_runtime(store)
        run_result = runtime.start_run(skill_ref, inputs)

        run_id = run_result["run_id"]
        run = store.get_run(run_id)
        assert run is not None
        assert run_result["status"] == "SUCCEEDED"
        assert run.status == "SUCCEEDED"

        events = store.list_events(run_id)
        assert any(event["type"] == "RUN_FINISHED" for event in events)

        main_event = next(event for event in events if event["type"] == expected_event)
        assert main_event["payload"]["step"] == expected_step

        if expected_event == "NOTIFY":
            assert main_event["payload"]["message"] == "notify smoke ok"
            return

        assert main_event["payload"]["tool"] == expected_tool
        assert main_event["payload"]["mcp"] == expected_mcp
        assert main_event["payload"]["result"]["ok"] is True


def test_assign_step_succeeds_from_external_skill_file() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        skill_path = Path(tmpdir) / "assign.yaml"
        skill_path.write_text(
            (
                "name: assign_demo\n"
                "inputs:\n"
                "  issue: string\n"
                "steps:\n"
                "  - id: start\n"
                "    type: assign\n"
                "    values:\n"
                "      action: retry\n"
                "      summary: '{{inputs.issue}}'\n"
                "      meta:\n"
                "        source: assign\n"
                "    next: done\n"
                "  - id: done\n"
                "    type: notify\n"
                "    message: '{{results.start.action}}'\n"
            ),
            encoding="utf-8",
        )

        store = SqliteStateStore(db_path)
        store.init_db()
        runtime = _build_runtime(store)

        run_result = runtime.start_run(str(skill_path), {"issue": "dependency timeout"}, skill_source="file")

        run = store.get_run(run_result["run_id"])
        assert run is not None
        assert run_result["status"] == "SUCCEEDED"
        assert run.context.results["start"] == {
            "action": "retry",
            "summary": "dependency timeout",
            "meta": {"source": "assign"},
        }

        events = store.list_events(run_result["run_id"])
        assign_event = next(event for event in events if event["type"] == "ASSIGN_RESULT")
        notify_event = next(event for event in events if event["type"] == "NOTIFY")

        assert assign_event["payload"]["step"] == "start"
        assert assign_event["payload"]["result"] == {
            "action": "retry",
            "summary": "dependency timeout",
            "meta": {"source": "assign"},
        }
        assert notify_event["payload"]["message"] == "retry"
