import pytest
from helpers.agent_config import agent_runner_config

from skiller.application.agent.context.agent_context_manager import AgentContextManager
from skiller.application.agent.prompt.prompt_builder import AgentPromptBuilder
from skiller.application.tools.notify import NotifyTool
from skiller.domain.agent.agent_context_model import (
    AgentAssistantMessagePayload,
    AgentContextEntry,
    AgentContextEntryType,
    AgentUserMessagePayload,
)
from skiller.domain.agent.agent_run_identity import AgentContext

pytestmark = pytest.mark.unit

NOTIFY_TOOL_DEFINITION = NotifyTool()


def test_agent_context_manager_builds_llm_request_from_current_context() -> None:
    store = _FakeAgentContextStore(
        entries=[
            AgentContextEntry(
                id="entry-1",
                run_id="run-1",
                context_id="ctx-1",
                sequence=1,
                entry_type=AgentContextEntryType.USER_MESSAGE,
                payload=AgentUserMessagePayload(text="Hello"),
                usage=None,
                source_step_id="agent-1",
                created_at="2026-05-16T00:00:00Z",
            )
        ],
        next_turn_id="turn-2",
    )
    manager = AgentContextManager(
        agent_context_store=store,
        prompt_builder=AgentPromptBuilder(),
    )
    context = AgentContext(
        run_id="run-1",
        agent_id="agent-1",
        context_id="ctx-1",
    )
    config = agent_runner_config(
        task="Task",
        system="Be useful.",
        max_turns=1,
        tools=(NOTIFY_TOOL_DEFINITION,),
    )

    result = manager.build_llm_request(context=context, config=config)

    assert result.turn_id == "turn-2"
    assert [message.role.value for message in result.llm_request.messages] == [
        "system",
        "user",
    ]
    assert result.llm_request.messages[0].content == "Be useful."
    assert result.llm_request.messages[1].content == "Hello"
    assert result.context_id == "ctx-1"
    assert result.context_window_tokens == 80_000
    assert result.max_ratio == 0.8
    assert result.estimated_tokens == 0
    assert [tool.name for tool in result.llm_request.tools] == ["notify"]


def test_agent_context_manager_builds_window_context_without_changing_default_request() -> None:
    store = _FakeAgentContextStore(
        entries=[
            AgentContextEntry(
                id="entry-1",
                run_id="run-1",
                context_id="ctx-1",
                sequence=1,
                entry_type=AgentContextEntryType.USER_MESSAGE,
                payload=AgentUserMessagePayload(text="Full context"),
                usage=None,
                source_step_id="agent-1",
                created_at="2026-05-16T00:00:00Z",
            )
        ],
        window_entries=[
            AgentContextEntry(
                id="entry-2",
                run_id="run-1",
                context_id="ctx-1",
                sequence=2,
                entry_type=AgentContextEntryType.USER_MESSAGE,
                payload=AgentUserMessagePayload(text="Window context"),
                usage=None,
                source_step_id="agent-1",
                created_at="2026-05-16T00:00:00Z",
            )
        ],
        next_turn_id="turn-3",
    )
    manager = AgentContextManager(
        agent_context_store=store,
        prompt_builder=AgentPromptBuilder(),
    )
    context = AgentContext(
        run_id="run-1",
        agent_id="agent-1",
        context_id="ctx-1",
    )
    config = agent_runner_config(
        task="Task",
        system="Be useful.",
        max_turns=1,
    )

    default_result = manager.build_llm_request(context=context, config=config)
    window_result = manager.build_window_context(context=context, config=config)

    assert default_result.llm_request.messages[1].content == "Full context"
    assert window_result.context_id == "ctx-1"
    assert window_result.turn_id == "turn-3"
    assert window_result.llm_request.messages[1].content == "Window context"
    assert window_result.context_window_tokens == 80_000
    assert window_result.max_ratio == 0.8
    assert window_result.estimated_tokens == 0
    assert store.window_calls == [{"context_id": "ctx-1", "window_tokens": 80_000}]


def test_agent_context_manager_estimates_window_tokens_from_final_totals() -> None:
    store = _FakeAgentContextStore(
        entries=[],
        window_entries=[
            AgentContextEntry(
                id="entry-1",
                run_id="run-1",
                context_id="ctx-1",
                sequence=1,
                entry_type=AgentContextEntryType.ASSISTANT_MESSAGE,
                payload=AgentAssistantMessagePayload(
                    turn_id="turn-1",
                    message_type="final",
                    text="First",
                    total_tokens=2,
                ),
                usage=None,
                source_step_id="agent-1",
                created_at="2026-05-16T00:00:00Z",
            ),
            AgentContextEntry(
                id="entry-2",
                run_id="run-1",
                context_id="ctx-1",
                sequence=2,
                entry_type=AgentContextEntryType.ASSISTANT_MESSAGE,
                payload=AgentAssistantMessagePayload(
                    turn_id="turn-2",
                    message_type="final",
                    text="Second",
                    total_tokens=6,
                ),
                usage=None,
                source_step_id="agent-1",
                created_at="2026-05-16T00:00:00Z",
            ),
        ],
        next_turn_id="turn-3",
    )
    manager = AgentContextManager(
        agent_context_store=store,
        prompt_builder=AgentPromptBuilder(),
    )
    context = AgentContext(
        run_id="run-1",
        agent_id="agent-1",
        context_id="ctx-1",
    )
    config = agent_runner_config(
        task="Task",
        system="Be useful.",
        max_turns=1,
    )

    result = manager.build_window_context(context=context, config=config)

    assert result.context_window_tokens == 80_000
    assert result.max_ratio == 0.8
    assert result.estimated_tokens == 4


class _FakeAgentContextStore:
    def __init__(
        self,
        *,
        entries: list[AgentContextEntry],
        next_turn_id: str,
        window_entries: list[AgentContextEntry] | None = None,
    ) -> None:
        self.entries = entries
        self.window_entries = window_entries or entries
        self.next = next_turn_id
        self.window_calls: list[dict[str, object]] = []

    def append_user_message(self, **kwargs):  # noqa: ANN003, ANN201
        raise NotImplementedError

    def append_assistant_message(self, **kwargs):  # noqa: ANN003, ANN201
        raise NotImplementedError

    def append_tool_call(self, **kwargs):  # noqa: ANN003, ANN201
        raise NotImplementedError

    def append_tool_result(self, **kwargs):  # noqa: ANN003, ANN201
        raise NotImplementedError

    def list_entries(self, *, context_id: str) -> list[AgentContextEntry]:
        _ = context_id
        return self.entries

    def list_context_window(
        self,
        *,
        context_id: str,
        window_tokens: int,
    ) -> list[AgentContextEntry]:
        self.window_calls.append(
            {
                "context_id": context_id,
                "window_tokens": window_tokens,
            }
        )
        return self.window_entries

    def next_turn_id(self, *, context_id: str) -> str:
        _ = context_id
        return self.next
