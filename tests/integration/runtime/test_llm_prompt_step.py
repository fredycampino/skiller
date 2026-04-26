from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from skiller.application.run_worker_service import RunWorkerService
from skiller.application.runtime_application_service import RuntimeApplicationService
from skiller.application.tools.notify import NotifyTool, NotifyToolAdapter
from skiller.application.tools.shell import ShellTool, ShellToolAdapter
from skiller.application.use_cases.agent.execute_agent_step import ExecuteAgentStepUseCase
from skiller.application.use_cases.agent.tool_manager import ToolManager
from skiller.application.use_cases.execute.execute_assign_step import ExecuteAssignStepUseCase
from skiller.application.use_cases.execute.execute_llm_prompt_step import (
    ExecuteLlmPromptStepUseCase,
)
from skiller.application.use_cases.execute.execute_mcp_step import ExecuteMcpStepUseCase
from skiller.application.use_cases.execute.execute_notify_step import ExecuteNotifyStepUseCase
from skiller.application.use_cases.execute.execute_shell_step import ExecuteShellStepUseCase
from skiller.application.use_cases.execute.execute_switch_step import ExecuteSwitchStepUseCase
from skiller.application.use_cases.execute.execute_wait_webhook_step import (
    ExecuteWaitWebhookStepUseCase,
)
from skiller.application.use_cases.execute.execute_when_step import ExecuteWhenStepUseCase
from skiller.application.use_cases.ingress.handle_webhook import HandleWebhookUseCase
from skiller.application.use_cases.query.get_run_status import GetRunStatusUseCase
from skiller.application.use_cases.query.list_webhooks import ListWebhooksUseCase
from skiller.application.use_cases.render.render_current_step import RenderCurrentStepUseCase
from skiller.application.use_cases.render.render_mcp_config import RenderMcpConfigUseCase
from skiller.application.use_cases.run.append_runtime_event import AppendRuntimeEventUseCase
from skiller.application.use_cases.run.bootstrap_runtime import BootstrapRuntimeUseCase
from skiller.application.use_cases.run.complete_run import CompleteRunUseCase
from skiller.application.use_cases.run.create_run import CreateRunUseCase
from skiller.application.use_cases.run.delete_run import DeleteRunUseCase
from skiller.application.use_cases.run.fail_run import FailRunUseCase
from skiller.application.use_cases.run.get_start_step import GetStartStepUseCase
from skiller.application.use_cases.run.resume_run import ResumeRunUseCase
from skiller.application.use_cases.skill.skill_checker import SkillCheckerUseCase
from skiller.application.use_cases.skill.skill_server_checker import SkillServerCheckerUseCase
from skiller.application.use_cases.webhook.register_webhook import RegisterWebhookUseCase
from skiller.application.use_cases.webhook.remove_webhook import RemoveWebhookUseCase
from skiller.di.container import build_runtime_container
from skiller.domain.large_result_truncator import LargeResultTruncator
from skiller.infrastructure.config.settings import Settings
from skiller.infrastructure.db.sqlite_agent_context_store import SqliteAgentContextStore
from skiller.infrastructure.db.sqlite_execution_output_store import SqliteExecutionOutputStore
from skiller.infrastructure.db.sqlite_state_store import SqliteStateStore
from skiller.infrastructure.db.sqlite_webhook_registry import SqliteWebhookRegistry
from skiller.infrastructure.llm.fake_llm import FakeLLM
from skiller.infrastructure.skills.filesystem_skill_runner import FilesystemSkillRunner
from skiller.infrastructure.tools.mcp.default_mcp import DefaultMCP
from skiller.infrastructure.tools.shell.default_shell import DefaultShellRunner

pytestmark = [
    pytest.mark.integration,
]


class _FakeServerStatus:
    def is_available(self) -> bool:
        return True


class _FakeChannelSender:
    def is_available(self, *, channel: str) -> bool:
        _ = channel
        return True


class _FakeLLM:
    def __init__(
        self,
        content: str = (
            '{"summary":"tests failing on auth",'
            '"severity":"high","next_action":"retry"}'
        ),
        responses: list[str] | None = None,
    ) -> None:
        self._responses = responses or [content]
        self._response_index = 0
        self.calls: list[dict[str, object]] = []

    def generate(
        self, messages: list[dict[str, str]], config: dict[str, object] | None = None
    ) -> dict[str, object]:
        self.calls.append({"messages": messages, "config": config})
        if self._response_index >= len(self._responses):
            raise AssertionError("Fake LLM received more calls than expected")
        content = self._responses[self._response_index]
        self._response_index += 1
        return {
            "ok": True,
            "content": content,
            "model": "fake-llm",
        }


def _build_runtime(store: SqliteStateStore, llm: _FakeLLM) -> RuntimeApplicationService:
    execution_output_store = SqliteExecutionOutputStore(store.db_path)
    execution_output_store.init_db()
    agent_context_store = SqliteAgentContextStore(store.db_path)
    skill_runner = FilesystemSkillRunner(
        skills_dir="skills",
        execution_output_store=execution_output_store,
    )
    webhook_registry = SqliteWebhookRegistry(store.db_path)
    mcp = DefaultMCP()
    shell = DefaultShellRunner()
    tool_manager = ToolManager(
        tools=[
            ShellTool(shell),
            NotifyTool(),
        ],
        adapters=[
            ShellToolAdapter(),
            NotifyToolAdapter(),
        ],
    )
    fail_run_use_case = FailRunUseCase(store)
    append_runtime_event_use_case = AppendRuntimeEventUseCase(store)
    complete_run_use_case = CompleteRunUseCase(store)
    render_current_step_use_case = RenderCurrentStepUseCase(store=store, skill_runner=skill_runner)
    render_mcp_config_use_case = RenderMcpConfigUseCase(store=store, skill_runner=skill_runner)
    execute_agent_step_use_case = ExecuteAgentStepUseCase(
        store=store,
        agent_context_store=agent_context_store,
        llm=llm,
        tool_manager=tool_manager,
    )
    execute_assign_step_use_case = ExecuteAssignStepUseCase(store=store)
    execute_llm_prompt_step_use_case = ExecuteLlmPromptStepUseCase(
        store=store,
        execution_output_store=execution_output_store,
        llm=llm,
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
    execute_wait_webhook_step_use_case = ExecuteWaitWebhookStepUseCase(
        run_store=store,
        wait_store=store,
        external_event_store=store,
    )
    run_worker_service = RunWorkerService(
        complete_run_use_case=complete_run_use_case,
        fail_run_use_case=fail_run_use_case,
        append_runtime_event_use_case=append_runtime_event_use_case,
        render_current_step_use_case=render_current_step_use_case,
        render_mcp_config_use_case=render_mcp_config_use_case,
        execute_agent_step_use_case=execute_agent_step_use_case,
        execute_assign_step_use_case=execute_assign_step_use_case,
        execute_llm_prompt_step_use_case=execute_llm_prompt_step_use_case,
        execute_mcp_step_use_case=execute_mcp_step_use_case,
        execute_notify_step_use_case=execute_notify_step_use_case,
        execute_shell_step_use_case=execute_shell_step_use_case,
        execute_switch_step_use_case=execute_switch_step_use_case,
        execute_when_step_use_case=execute_when_step_use_case,
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
        delete_run_use_case=DeleteRunUseCase(store),
        fail_run_use_case=fail_run_use_case,
        get_start_step_use_case=GetStartStepUseCase(store=store),
        skill_checker_use_case=SkillCheckerUseCase(skill_runner=skill_runner),
        skill_server_checker_use_case=SkillServerCheckerUseCase(
            skill_runner=skill_runner,
            server_status=_FakeServerStatus(),
            channel_sender=_FakeChannelSender(),
        ),
        handle_webhook_use_case=HandleWebhookUseCase(
            external_event_store=store,
            wait_store=store,
        ),
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
                "start: analyze_issue\n"
                "inputs:\n"
                "  stderr: string\n"
                "steps:\n"
                "  - llm_prompt: analyze_issue\n"
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
                "  - notify: done\n"
                '    message: \'{{output_value("analyze_issue").data.next_action}}\'\n'
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
        assert run.context.step_executions["analyze_issue"].output.to_public_dict() == {
            "text": (
                '{"next_action": "retry", "severity": "high", '
                '"summary": "tests failing on auth"}'
            ),
            "value": {
                "data": {
                    "summary": "tests failing on auth",
                    "severity": "high",
                    "next_action": "retry",
                }
            },
            "body_ref": None,
        }

        events = store.list_events(run_result["run_id"])
        llm_event = next(
            event
            for event in events
            if event["type"] == "STEP_SUCCESS" and event["payload"]["step"] == "analyze_issue"
        )
        notify_event = next(
            event
            for event in events
            if event["type"] == "STEP_SUCCESS" and event["payload"]["step"] == "done"
        )

        assert llm_event["payload"]["output"]["value"]["data"]["severity"] == "high"
        assert notify_event["payload"]["output"]["value"]["message"] == "retry"
        assert llm.calls[0]["messages"][1]["content"].endswith("Traceback auth failed\n")


def test_agent_step_succeeds_and_persists_agent_context() -> None:
    llm = _FakeLLM(content='{"reply":"Hola, claro."}')

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        skill_path = Path(tmpdir) / "agent.yaml"
        skill_path.write_text(
            (
                "name: agent_demo\n"
                "start: support_agent\n"
                "inputs:\n"
                "  message: string\n"
                "  thread_id: string\n"
                "steps:\n"
                "  - agent: support_agent\n"
                "    system: |\n"
                "      You are a helpful WhatsApp assistant.\n"
                "      Reply in the same language as the incoming message.\n"
                "    task: '{{inputs.message}}'\n"
                "    context_id: '{{inputs.thread_id}}'\n"
                "    max_turns: 1\n"
                "    next: done\n"
                "  - notify: done\n"
                '    message: \'{{output_value("support_agent").data.final.text}}\'\n'
            ),
            encoding="utf-8",
        )

        store = SqliteStateStore(db_path)
        store.init_db()
        runtime = _build_runtime(store, llm)

        run_result = runtime.run(
            str(skill_path),
            {"message": "Hola", "thread_id": "chat-1"},
            skill_source="file",
        )

        run = store.get_run(run_result["run_id"])
        agent_context_store = SqliteAgentContextStore(store.db_path)
        entries = agent_context_store.list_entries(
            run_id=run_result["run_id"],
            context_id="chat-1",
        )

        assert run_result["status"] == "SUCCEEDED"
        assert run is not None
        assert run.context.step_executions["support_agent"].output.to_public_dict() == {
            "text": "Hola, claro.",
            "value": {
                "data": {
                    "context_id": "chat-1",
                    "final": {"text": "Hola, claro."},
                    "turn_count": 1,
                    "tool_call_count": 0,
                    "stop_reason": "final",
                }
            },
            "body_ref": None,
            "text_ref": "data.final.text",
        }
        assert run.context.step_executions["done"].output.to_public_dict()["value"] == {
            "message": "Hola, claro."
        }
        assert [entry.entry_type.value for entry in entries] == [
            "user_message",
            "assistant_message",
        ]
        assert entries[0].payload == {"type": "user_message", "text": "Hola"}
        assert entries[1].payload == {
            "type": "assistant_message",
            "turn_id": "turn-1",
            "text": "Hola, claro.",
        }
        assert llm.calls[0]["messages"] == [
            {
                "role": "system",
                "content": (
                    "You are a helpful WhatsApp assistant.\n"
                    "Reply in the same language as the incoming message.\n"
                ),
            },
            {"role": "user", "content": "Hola"},
        ]


def test_agent_step_executes_tool_then_succeeds_and_persists_context() -> None:
    llm = _FakeLLM(
        responses=[
            '{"type":"tool_call","tool":"notify","args":{"message":"Abrimos un ticket interno."}}',
            '{"type":"success","text":"Ya registré una nota interna y sigo disponible."}',
        ]
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        skill_path = Path(tmpdir) / "agent_tools.yaml"
        skill_path.write_text(
            (
                "name: agent_tools_demo\n"
                "start: support_agent\n"
                "inputs:\n"
                "  message: string\n"
                "  thread_id: string\n"
                "steps:\n"
                "  - agent: support_agent\n"
                "    system: |\n"
                "      You are a helpful support assistant.\n"
                "      Keep responses concise.\n"
                "    task: '{{inputs.message}}'\n"
                "    context_id: '{{inputs.thread_id}}'\n"
                "    tools:\n"
                "      - notify\n"
                "    max_turns: 3\n"
                "    next: done\n"
                "  - notify: done\n"
                '    message: \'{{output_value("support_agent").data.final.text}}\'\n'
            ),
            encoding="utf-8",
        )

        store = SqliteStateStore(db_path)
        store.init_db()
        runtime = _build_runtime(store, llm)

        run_result = runtime.run(
            str(skill_path),
            {"message": "Necesito que lo revises", "thread_id": "chat-tools-1"},
            skill_source="file",
        )

        run = store.get_run(run_result["run_id"])
        agent_context_store = SqliteAgentContextStore(store.db_path)
        entries = agent_context_store.list_entries(
            run_id=run_result["run_id"],
            context_id="chat-tools-1",
        )

        assert run_result["status"] == "SUCCEEDED"
        assert run is not None
        assert run.context.step_executions["support_agent"].output.to_public_dict() == {
            "text": "Ya registré una nota interna y sigo disponible.",
            "value": {
                "data": {
                    "context_id": "chat-tools-1",
                    "final": {"text": "Ya registré una nota interna y sigo disponible."},
                    "turn_count": 2,
                    "tool_call_count": 1,
                    "stop_reason": "success",
                }
            },
            "body_ref": None,
            "text_ref": "data.final.text",
        }
        assert run.context.step_executions["done"].output.to_public_dict()["value"] == {
            "message": "Ya registré una nota interna y sigo disponible."
        }
        assert [entry.entry_type.value for entry in entries] == [
            "user_message",
            "tool_call",
            "tool_result",
            "assistant_message",
        ]
        assert entries[0].payload == {
            "type": "user_message",
            "text": "Necesito que lo revises",
        }
        assert entries[1].payload == {
            "type": "tool_call",
            "turn_id": "turn-1",
            "tool": "notify",
            "args": {"message": "Abrimos un ticket interno."},
        }
        assert entries[2].payload == {
            "type": "tool_result",
            "turn_id": "turn-1",
            "tool": "notify",
            "status": "COMPLETED",
            "data": {"message": "Abrimos un ticket interno."},
            "text": "Abrimos un ticket interno.",
            "error": None,
        }
        assert entries[3].payload == {
            "type": "assistant_message",
            "turn_id": "turn-2",
            "text": "Ya registré una nota interna y sigo disponible.",
        }
        assert len(llm.calls) == 2
        assert llm.calls[0]["config"] == {
            "step_id": "support_agent",
            "agent": True,
            "max_turns": 3,
            "tools": ["notify"],
        }
        assert llm.calls[0]["messages"] == [
            {
                "role": "system",
                "content": (
                    "You are a helpful support assistant.\n"
                    "Keep responses concise.\n\n"
                    "If you need to use a tool, reply with exactly one JSON object and no "
                    "extra text.\n"
                    'The only structured tool response type is "tool_call".\n'
                    "Allowed tools are: notify.\n"
                    'Use only tool names from this list: ["notify"].\n'
                    'For a tool call respond with '
                    '{"type":"tool_call","tool":"<tool>","args":{...}}.\n'
                    'Example tool call: {"type":"tool_call","tool":"shell",'
                    '"args":{"command":"pytest -q"}}.\n'
                    "When the task is complete, answer the user directly in plain text.\n"
                    "Do not wrap the final answer in JSON unless you are making a tool call.\n"
                    "If a tool fails, use the returned tool_result to decide whether to try "
                    "another tool or continue reasoning. "
                    "Do not emit an error terminal response."
                ),
            },
            {"role": "user", "content": "Necesito que lo revises"},
        ]
        assert llm.calls[1]["messages"] == [
            llm.calls[0]["messages"][0],
            {"role": "user", "content": "Necesito que lo revises"},
            {
                "role": "assistant",
                "content": (
                    '{"args": {"message": "Abrimos un ticket interno."}, "tool": "notify", '
                    '"turn_id": "turn-1", "type": "tool_call"}'
                ),
            },
            {
                "role": "user",
                "content": (
                    '{"data": {"message": "Abrimos un ticket interno."}, "error": null, '
                    '"status": "COMPLETED", "text": "Abrimos un ticket interno.", '
                    '"tool": "notify", "turn_id": "turn-1", "type": "tool_result"}'
                ),
            },
        ]


def test_llm_prompt_step_persists_large_result_body_and_truncates_output_value() -> None:
    llm = _FakeLLM()

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        skill_path = Path(tmpdir) / "llm_prompt_large.yaml"
        skill_path.write_text(
            (
                "name: llm_prompt_large_demo\n"
                "start: analyze_issue\n"
                "inputs:\n"
                "  stderr: string\n"
                "steps:\n"
                "  - llm_prompt: analyze_issue\n"
                "    prompt: '{{inputs.stderr}}'\n"
                "    large_result: true\n"
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
                "          next_action:\n"
                "            type: string\n"
                "    next: done\n"
                "  - notify: done\n"
                '    message: \'{{output_value("analyze_issue").data.summary}}\'\n'
            ),
            encoding="utf-8",
        )

        store = SqliteStateStore(db_path)
        store.init_db()
        runtime = _build_runtime(store, llm)
        execution_output_store = SqliteExecutionOutputStore(store.db_path)

        run_result = runtime.run(
            str(skill_path), {"stderr": "Traceback auth failed"}, skill_source="file"
        )

        run = store.get_run(run_result["run_id"])
        assert run_result["status"] == "SUCCEEDED"
        assert run is not None
        body_ref = run.context.step_executions["analyze_issue"].output.body_ref
        assert isinstance(body_ref, str)
        assert body_ref.startswith("execution_output:")
        assert run.context.step_executions["analyze_issue"].output.to_public_dict() == {
            "text": (
                '{"next_action": "retry", "severity": "high", '
                '"summary": "tests failing on auth", "truncated": true}'
            ),
            "value": {
                "data": {
                    "truncated": True,
                    "summary": "tests failing on auth",
                    "severity": "high",
                    "next_action": "retry",
                }
            },
            "body_ref": body_ref,
        }
        assert execution_output_store.get_execution_output(body_ref) == {
            "value": {
                "data": {
                    "summary": "tests failing on auth",
                    "severity": "high",
                    "next_action": "retry",
                }
            },
        }


def test_llm_prompt_step_succeeds_with_fake_llm_provider_from_container() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        skill_path = Path(tmpdir) / "llm_prompt.yaml"
        skill_path.write_text(
            (
                "name: llm_prompt_demo\n"
                "start: analyze_issue\n"
                "inputs:\n"
                "  stderr: string\n"
                "steps:\n"
                "  - llm_prompt: analyze_issue\n"
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
                "  - notify: done\n"
                '    message: \'{{output_value("analyze_issue").data.next_action}}\'\n'
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
        assert run.context.step_executions["analyze_issue"].output.to_public_dict() == {
            "text": (
                '{"next_action": "ask_human", "severity": "medium", '
                '"summary": "container fake"}'
            ),
            "value": {
                "data": {
                    "summary": "container fake",
                    "severity": "medium",
                    "next_action": "ask_human",
                }
            },
            "body_ref": None,
        }

        events = container.query_service.get_run_logs_use_case.execute(run_result["run_id"])
        llm_event = next(
            event
            for event in events
            if event["type"] == "STEP_SUCCESS" and event["payload"]["step"] == "analyze_issue"
        )
        notify_event = next(
            event
            for event in events
            if event["type"] == "STEP_SUCCESS" and event["payload"]["step"] == "done"
        )

        assert llm_event["payload"]["output"]["value"]["data"]["next_action"] == "ask_human"
        assert notify_event["payload"]["output"]["value"]["message"] == "ask_human"


def test_llm_prompt_failure_persists_step_error_and_run_finished() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        skill_path = Path(tmpdir) / "llm_prompt.yaml"
        skill_path.write_text(
            (
                "name: llm_prompt_demo\n"
                "start: analyze_issue\n"
                "inputs:\n"
                "  issue: string\n"
                "steps:\n"
                "  - llm_prompt: analyze_issue\n"
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
            "step": "analyze_issue",
            "step_type": "llm_prompt",
            "error": "LLM step 'analyze_issue' returned invalid JSON: Expecting value",
        }
        assert failed_event["payload"] == {
            "status": "FAILED",
            "error": "LLM step 'analyze_issue' returned invalid JSON: Expecting value",
        }


def test_llm_prompt_step_accepts_markdown_fenced_json_from_provider() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        skill_path = Path(tmpdir) / "llm_prompt.yaml"
        skill_path.write_text(
            (
                "name: llm_prompt_demo\n"
                "start: analyze_issue\n"
                "inputs:\n"
                "  issue: string\n"
                "steps:\n"
                "  - llm_prompt: analyze_issue\n"
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
                "  - notify: done\n"
                '    message: \'{{output_value("analyze_issue").data.next_action}}\'\n'
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
            if event["type"] == "STEP_SUCCESS" and event["payload"]["step"] == "analyze_issue"
        )

        assert run_result["status"] == "SUCCEEDED"
        assert run is not None
        assert run.context.step_executions["analyze_issue"].output.to_public_dict() == {
            "text": '{"next_action": "retry", "severity": "low", "summary": "ok"}',
            "value": {
                "data": {
                    "summary": "ok",
                    "severity": "low",
                    "next_action": "retry",
                }
            },
            "body_ref": None,
        }
        assert llm_event["payload"]["output"]["value"]["data"]["next_action"] == "retry"
