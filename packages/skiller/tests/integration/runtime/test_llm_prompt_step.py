from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from helpers.agent_runner import build_agent_runner

from skiller.application.agent.config.step_config_reader import AGENT_RUNTIME_SYSTEM
from skiller.application.agent.tools.tool_manager import ToolManager
from skiller.application.run_worker_service import RunWorkerService
from skiller.application.runtime_application_service import RuntimeApplicationService
from skiller.application.tools.notify import NotifyTool
from skiller.application.tools.shell import ShellProcessTool
from skiller.application.use_cases.execute.execute_agent_step import (
    ExecuteAgentStepUseCase,
)
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
from skiller.domain.agent.agent_context_model import agent_context_payload_to_dict
from skiller.domain.agent.llm_model import (
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMToolCall,
    LLMToolCallFunction,
)
from skiller.domain.event.event_model import (
    RunFinishedPayload,
    StepErrorPayload,
    StepSuccessPayload,
)
from skiller.infrastructure.config.settings import Settings
from skiller.infrastructure.db.sqlite_agent_context_store import SqliteAgentContextStore
from skiller.infrastructure.db.sqlite_agent_steering_store import SqliteAgentSteeringStore
from skiller.infrastructure.db.sqlite_external_event_store import SqliteExternalEventStore
from skiller.infrastructure.db.sqlite_runtime_event_store import SqliteRuntimeEventStore
from skiller.infrastructure.db.sqlite_state_store import SqliteStateStore
from skiller.infrastructure.db.sqlite_webhook_registry import SqliteWebhookRegistry
from skiller.infrastructure.llm.fake_llm import FakeLLM
from skiller.infrastructure.skills.filesystem_skill_runner import FilesystemSkillRunner
from skiller.infrastructure.tools.mcp.default_mcp import DefaultMCP
from skiller.infrastructure.tools.process import DefaultToolProcessRunner

pytestmark = [
    pytest.mark.integration,
]


def _assert_system_message_contains(
    message: LLMMessage,
    *,
    step_system: str,
) -> None:
    assert message.role.value == "system"
    assert AGENT_RUNTIME_SYSTEM in (message.content or "")
    assert step_system.strip() in (message.content or "")


class _FakeServerStatus:
    def is_available(self) -> bool:
        return True


class _FakeChannelSender:
    def is_available(self, *, channel: str) -> bool:
        _ = channel
        return True


def _event_store(store: SqliteStateStore) -> SqliteRuntimeEventStore:
    return SqliteRuntimeEventStore(store.db_path)


class _FakeLLM:
    def __init__(
        self,
        content: str = (
            '{"summary":"tests failing on auth","severity":"high","next_action":"retry"}'
        ),
        responses: list[str] | None = None,
    ) -> None:
        self._responses = responses or [content]
        self._response_index = 0
        self.calls: list[object] = []

    def generate(self, request_or_messages, config: dict[str, object] | None = None):  # noqa: ANN001
        if isinstance(request_or_messages, LLMRequest):
            self.calls.append(request_or_messages)
            if self._response_index >= len(self._responses):
                raise AssertionError("Fake LLM received more calls than expected")
            content = self._responses[self._response_index]
            self._response_index += 1
            if isinstance(content, LLMResponse):
                return content
            return LLMResponse(ok=True, content=content, model="fake-llm")

        messages = request_or_messages
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
    runtime_event_store = SqliteRuntimeEventStore(store.db_path)
    external_event_store = SqliteExternalEventStore(store.db_path)
    agent_context_store = SqliteAgentContextStore(store.db_path)
    agent_steering_store = SqliteAgentSteeringStore(store.db_path)
    skill_runner = FilesystemSkillRunner(
        skills_dir="skills",
    )
    webhook_registry = SqliteWebhookRegistry(store.db_path)
    mcp = DefaultMCP()
    shell_tool = ShellProcessTool()
    tool_process_runner = DefaultToolProcessRunner()
    tool_manager = ToolManager(
        tools=[
            shell_tool,
            NotifyTool(),
        ],
    )
    fail_run_use_case = FailRunUseCase(store)
    append_runtime_event_use_case = AppendRuntimeEventUseCase(runtime_event_store)
    complete_run_use_case = CompleteRunUseCase(store)
    render_current_step_use_case = RenderCurrentStepUseCase(store=store, skill_runner=skill_runner)
    render_mcp_config_use_case = RenderMcpConfigUseCase(store=store, skill_runner=skill_runner)
    execute_agent_step_use_case = ExecuteAgentStepUseCase(
        store=store,
        runner=build_agent_runner(
            agent_context_store=agent_context_store,
            llm=llm,
            tool_manager=tool_manager,
            append_runtime_event_use_case=append_runtime_event_use_case,
        ),
    )
    execute_assign_step_use_case = ExecuteAssignStepUseCase(store=store)
    execute_llm_prompt_step_use_case = ExecuteLlmPromptStepUseCase(
        store=store,
        llm=llm,
    )
    execute_mcp_step_use_case = ExecuteMcpStepUseCase(
        store=store,
        mcp=mcp,
    )
    execute_notify_step_use_case = ExecuteNotifyStepUseCase(store=store)
    execute_shell_step_use_case = ExecuteShellStepUseCase(
        store=store,
        shell_tool=shell_tool,
        process_runner=tool_process_runner,
        agent_steering_store=agent_steering_store,
    )
    execute_switch_step_use_case = ExecuteSwitchStepUseCase(store=store)
    execute_when_step_use_case = ExecuteWhenStepUseCase(store=store)
    execute_wait_webhook_step_use_case = ExecuteWaitWebhookStepUseCase(
        run_store=store,
        wait_store=store,
        external_event_store=external_event_store,
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
            external_event_store=external_event_store,
            wait_store=store,
        ),
        list_webhooks_use_case=ListWebhooksUseCase(registry=webhook_registry),
        register_webhook_use_case=RegisterWebhookUseCase(registry=webhook_registry),
        remove_webhook_use_case=RemoveWebhookUseCase(registry=webhook_registry),
        resume_run_use_case=ResumeRunUseCase(store=store),
        interrupt_agent_use_case=SimpleNamespace(execute=lambda run_id: None),
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
                "    message: '{{output_value(\"analyze_issue\").data.next_action}}'\n"
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
                '{"next_action": "retry", "severity": "high", "summary": "tests failing on auth"}'
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

        events = _event_store(store).list_events(run_result["run_id"])
        llm_event = _step_success_event(events, step_id="analyze_issue")
        notify_event = _step_success_event(events, step_id="done")

        assert llm_event.payload.output["value"]["data"]["severity"] == "high"
        assert notify_event.payload.output["value"]["message"] == "retry"
        assert llm.calls[0]["messages"][1]["content"].endswith("Traceback auth failed\n")


def test_agent_step_succeeds_and_persists_agent_context() -> None:
    llm = _FakeLLM(content="Hola, claro.")

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
                "    message: '{{output_value(\"support_agent\").data.final.text}}'\n"
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
            scope=SimpleNamespace(
                run_id=run_result["run_id"],
                agent_id="support_agent",
                context_id="chat-1",
            ),
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
        assert agent_context_payload_to_dict(entries[0].payload) == {
            "type": "user_message",
            "text": "Hola",
        }
        assert agent_context_payload_to_dict(entries[1].payload) == {
            "type": "assistant_message",
            "turn_id": "turn-1",
            "message_type": "final",
            "text": "Hola, claro.",
        }
        _assert_system_message_contains(
            llm.calls[0].messages[0],
            step_system=(
                "You are a helpful WhatsApp assistant.\n"
                "Reply in the same language as the incoming message.\n"
            ),
        )
        assert llm.calls[0].messages[1:] == (LLMMessage.user("Hola"),)


def test_agent_step_executes_tool_then_succeeds_and_persists_context() -> None:
    llm = _FakeLLM(
        responses=[
            LLMResponse(
                ok=True,
                model="fake",
                tool_calls=(
                    LLMToolCall(
                        id="openai-call-1",
                        function=LLMToolCallFunction(
                            name="notify",
                            arguments_json='{"message":"Abrimos un ticket interno."}',
                        ),
                    ),
                ),
                finish_reason="tool_calls",
            ),
            LLMResponse(
                ok=True,
                content="Ya registré una nota interna y sigue disponible.",
                model="fake",
            ),
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
                "    message: '{{output_value(\"support_agent\").data.final.text}}'\n"
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
            scope=SimpleNamespace(
                run_id=run_result["run_id"],
                agent_id="support_agent",
                context_id="chat-tools-1",
            ),
        )

        assert run_result["status"] == "SUCCEEDED"
        assert run is not None
        assert run.context.step_executions["support_agent"].output.to_public_dict() == {
            "text": "Ya registré una nota interna y sigue disponible.",
            "value": {
                "data": {
                    "context_id": "chat-tools-1",
                    "final": {"text": "Ya registré una nota interna y sigue disponible."},
                    "turn_count": 2,
                    "tool_call_count": 1,
                    "stop_reason": "final",
                }
            },
            "body_ref": None,
            "text_ref": "data.final.text",
        }
        assert run.context.step_executions["done"].output.to_public_dict()["value"] == {
            "message": "Ya registré una nota interna y sigue disponible."
        }
        assert [entry.entry_type.value for entry in entries] == [
            "user_message",
            "tool_call",
            "tool_result",
            "assistant_message",
        ]
        assert agent_context_payload_to_dict(entries[0].payload) == {
            "type": "user_message",
            "text": "Necesito que lo revises",
        }
        assert agent_context_payload_to_dict(entries[1].payload) == {
            "type": "tool_call",
            "turn_id": "turn-1",
            "parent_sequence": None,
            "tool_call_id": "openai-call-1",
            "tool": "notify",
            "args": {"message": "Abrimos un ticket interno."},
        }
        assert agent_context_payload_to_dict(entries[2].payload) == {
            "type": "tool_result",
            "turn_id": "turn-1",
            "parent_sequence": None,
            "tool_call_id": "openai-call-1",
            "tool": "notify",
            "status": "COMPLETED",
            "data": {"message": "Abrimos un ticket interno."},
            "text": "Abrimos un ticket interno.",
            "error": None,
        }
        assert agent_context_payload_to_dict(entries[3].payload) == {
            "type": "assistant_message",
            "turn_id": "turn-2",
            "message_type": "final",
            "text": "Ya registré una nota interna y sigue disponible.",
        }
        assert len(llm.calls) == 2
        _assert_system_message_contains(
            llm.calls[0].messages[0],
            step_system=("You are a helpful support assistant.\nKeep responses concise.\n"),
        )
        assert llm.calls[0].messages[1] == LLMMessage.user("Necesito que lo revises")
        assert [tool.name for tool in llm.calls[0].tools] == ["notify"]
        assert llm.calls[1].messages == (
            llm.calls[0].messages[0],
            LLMMessage.user("Necesito que lo revises"),
            LLMMessage.assistant(
                tool_calls=(
                    LLMToolCall(
                        id="openai-call-1",
                        function=LLMToolCallFunction(
                            name="notify",
                            arguments_json='{"message": "Abrimos un ticket interno."}',
                        ),
                    ),
                )
            ),
            LLMMessage.tool(
                "Abrimos un ticket interno.",
                tool_call_id="openai-call-1",
            ),
        )
        assert [tool.name for tool in llm.calls[1].tools] == ["notify"]


def test_agent_step_preserves_assistant_content_with_tool_call_in_context() -> None:
    llm = _FakeLLM(
        responses=[
            LLMResponse(
                ok=True,
                content="I should send a note first.",
                model="fake",
                tool_calls=(
                    LLMToolCall(
                        id="openai-call-1",
                        function=LLMToolCallFunction(
                            name="notify",
                            arguments_json='{"message":"Abrimos un ticket interno."}',
                        ),
                    ),
                ),
                finish_reason="tool_calls",
            ),
            LLMResponse(
                ok=True,
                content="Ya registré una nota interna y sigue disponible.",
                model="fake",
            ),
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
                "    message: '{{output_value(\"support_agent\").data.final.text}}'\n"
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
            scope=SimpleNamespace(
                run_id=run_result["run_id"],
                agent_id="support_agent",
                context_id="chat-tools-1",
            ),
        )

        assert run_result["status"] == "SUCCEEDED"
        assert run is not None
        assert [entry.entry_type.value for entry in entries] == [
            "user_message",
            "assistant_message",
            "tool_call",
            "tool_result",
            "assistant_message",
        ]
        assert agent_context_payload_to_dict(entries[1].payload) == {
            "type": "assistant_message",
            "turn_id": "turn-1",
            "message_type": "tool_calls",
            "text": "I should send a note first.",
        }
        assert llm.calls[1].messages == (
            llm.calls[0].messages[0],
            LLMMessage.user("Necesito que lo revises"),
            LLMMessage.assistant(
                "I should send a note first.",
                tool_calls=(
                    LLMToolCall(
                        id="openai-call-1",
                        function=LLMToolCallFunction(
                            name="notify",
                            arguments_json='{"message": "Abrimos un ticket interno."}',
                        ),
                    ),
                ),
            ),
            LLMMessage.tool(
                "Abrimos un ticket interno.",
                tool_call_id="openai-call-1",
            ),
        )


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
                "    message: '{{output_value(\"analyze_issue\").data.next_action}}'\n"
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
                '{"next_action": "ask_human", "severity": "medium", "summary": "container fake"}'
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
        llm_event = _step_success_event(events, step_id="analyze_issue")
        notify_event = _step_success_event(events, step_id="done")

        assert llm_event.payload.output["value"]["data"]["next_action"] == "ask_human"
        assert notify_event.payload.output["value"]["message"] == "ask_human"


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
        llm_error_event = next(event for event in events if event.type == "STEP_ERROR")
        failed_event = next(event for event in events if event.type == "RUN_FINISHED")

        assert run_result["status"] == "FAILED"
        assert run is not None
        assert run.status == "FAILED"
        assert llm_error_event.step_id == "analyze_issue"
        assert llm_error_event.step_type == "llm_prompt"
        assert llm_error_event.payload == StepErrorPayload(
            error="LLM step 'analyze_issue' returned invalid JSON: Expecting value"
        )
        assert failed_event.payload == RunFinishedPayload(
            status="FAILED",
            error="LLM step 'analyze_issue' returned invalid JSON: Expecting value",
        )


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
                "    message: '{{output_value(\"analyze_issue\").data.next_action}}'\n"
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
        llm_event = _step_success_event(events, step_id="analyze_issue")

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
        assert llm_event.payload.output["value"]["data"]["next_action"] == "retry"


def _step_success_event(events: list[object], *, step_id: str):
    event = next(
        event
        for event in events
        if event.type == "STEP_SUCCESS" and event.step_id == step_id
    )
    assert isinstance(event.payload, StepSuccessPayload)
    return event
