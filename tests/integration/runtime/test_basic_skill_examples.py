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
    fail_run_use_case = FailRunUseCase(store)
    append_runtime_event_use_case = AppendRuntimeEventUseCase(store)
    complete_run_use_case = CompleteRunUseCase(store)
    render_current_step_use_case = RenderCurrentStepUseCase(store=store, skill_runner=skill_runner)
    render_mcp_config_use_case = RenderMcpConfigUseCase(store=store, skill_runner=skill_runner)
    execute_assign_step_use_case = ExecuteAssignStepUseCase(store=store)
    execute_llm_prompt_step_use_case = ExecuteLlmPromptStepUseCase(store=store, llm=NullLLM())
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


@pytest.mark.parametrize(("skill_ref", "inputs"), [("notify_test", {})])
def test_basic_skill_examples_succeed(
    skill_ref: str,
    inputs: dict[str, str],
) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        store = SqliteStateStore(db_path)
        store.init_db()

        runtime = _build_runtime(store)
        run_result = runtime.run(skill_ref, inputs)

        run_id = run_result["run_id"]
        run = store.get_run(run_id)
        assert run is not None
        assert run_result["status"] == "SUCCEEDED"
        assert run.status == "SUCCEEDED"

        events = store.list_events(run_id)
        assert any(event["type"] == "RUN_FINISHED" for event in events)
        assert any(event["type"] == "STEP_STARTED" for event in events)
        assert any(event["type"] == "STEP_SUCCESS" for event in events)

        main_event = next(
            event
            for event in events
            if event["type"] == "STEP_SUCCESS" and event["payload"]["step"] == "start"
        )
        assert main_event["payload"] == {
            "step": "start",
            "step_type": "notify",
            "result": {"message": "notify smoke ok"},
        }


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

        run_result = runtime.run(
            str(skill_path), {"issue": "dependency timeout"}, skill_source="file"
        )

        run = store.get_run(run_result["run_id"])
        assert run is not None
        assert run_result["status"] == "SUCCEEDED"
        assert run.context.results["start"] == {
            "action": "retry",
            "summary": "dependency timeout",
            "meta": {"source": "assign"},
        }

        events = store.list_events(run_result["run_id"])
        assign_event = next(
            event
            for event in events
            if event["type"] == "STEP_SUCCESS" and event["payload"]["step"] == "start"
        )
        notify_event = next(
            event
            for event in events
            if event["type"] == "STEP_SUCCESS" and event["payload"]["step"] == "done"
        )

        assert assign_event["payload"] == {
            "step": "start",
            "step_type": "assign",
            "result": {
                "value": {
                    "action": "retry",
                    "summary": "dependency timeout",
                    "meta": {"source": "assign"},
                }
            },
            "next": "done",
        }
        assert notify_event["payload"]["result"]["message"] == "retry"


def test_switch_step_routes_to_matching_branch_from_external_skill_file() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        skill_path = Path(tmpdir) / "switch.yaml"
        skill_path.write_text(
            (
                "name: switch_demo\n"
                "steps:\n"
                "  - id: start\n"
                "    type: assign\n"
                "    values:\n"
                "      action: retry\n"
                "    next: decide_action\n"
                "  - id: decide_action\n"
                "    type: switch\n"
                '    value: "{{results.start.action}}"\n'
                "    cases:\n"
                "      retry: retry_notice\n"
                "      ask_human: human_notice\n"
                "    default: unknown_action\n"
                "  - id: retry_notice\n"
                "    type: notify\n"
                "    message: retry chosen\n"
                "  - id: human_notice\n"
                "    type: notify\n"
                "    message: human chosen\n"
                "  - id: unknown_action\n"
                "    type: notify\n"
                "    message: unknown chosen\n"
            ),
            encoding="utf-8",
        )

        store = SqliteStateStore(db_path)
        store.init_db()
        runtime = _build_runtime(store)

        run_result = runtime.run(str(skill_path), {}, skill_source="file")

        run = store.get_run(run_result["run_id"])
        assert run is not None
        assert run_result["status"] == "SUCCEEDED"
        assert run.context.results["decide_action"] == {
            "value": "retry",
            "next": "retry_notice",
        }

        events = store.list_events(run_result["run_id"])
        switch_event = next(
            event
            for event in events
            if event["type"] == "STEP_SUCCESS" and event["payload"]["step"] == "decide_action"
        )
        notify_event = next(
            event
            for event in events
            if event["type"] == "STEP_SUCCESS" and event["payload"]["step"] == "retry_notice"
        )

        assert switch_event["payload"] == {
            "step": "decide_action",
            "step_type": "switch",
            "result": {"next": "retry_notice"},
            "next": "retry_notice",
        }
        assert notify_event["payload"]["result"]["message"] == "retry chosen"


def test_when_step_routes_to_first_matching_branch_from_external_skill_file() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        skill_path = Path(tmpdir) / "when.yaml"
        skill_path.write_text(
            (
                "name: when_demo\n"
                "steps:\n"
                "  - id: start\n"
                "    type: assign\n"
                "    values:\n"
                "      score: 85\n"
                "    next: decide_score\n"
                "  - id: decide_score\n"
                "    type: when\n"
                '    value: "{{results.start.score}}"\n'
                "    branches:\n"
                "      - gt: 90\n"
                "        then: excellent\n"
                "      - gt: 70\n"
                "        then: good\n"
                "    default: fail\n"
                "  - id: excellent\n"
                "    type: notify\n"
                "    message: excellent chosen\n"
                "  - id: good\n"
                "    type: notify\n"
                "    message: good chosen\n"
                "  - id: fail\n"
                "    type: notify\n"
                "    message: fail chosen\n"
            ),
            encoding="utf-8",
        )

        store = SqliteStateStore(db_path)
        store.init_db()
        runtime = _build_runtime(store)

        run_result = runtime.run(str(skill_path), {}, skill_source="file")

        run = store.get_run(run_result["run_id"])
        assert run is not None
        assert run_result["status"] == "SUCCEEDED"
        assert run.context.results["decide_score"] == {
            "value": 85,
            "next": "good",
        }

        events = store.list_events(run_result["run_id"])
        when_event = next(
            event
            for event in events
            if event["type"] == "STEP_SUCCESS" and event["payload"]["step"] == "decide_score"
        )
        notify_event = next(
            event
            for event in events
            if event["type"] == "STEP_SUCCESS" and event["payload"]["step"] == "good"
        )

        assert when_event["payload"] == {
            "step": "decide_score",
            "step_type": "when",
            "result": {"next": "good"},
            "next": "good",
        }
        assert notify_event["payload"]["result"]["message"] == "good chosen"
