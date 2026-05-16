import pytest
from helpers.agent_config import agent_runner_config

from skiller.application.agent.context.agent_context_manager import AgentContextManager
from skiller.application.agent.prompt.prompt_builder import AgentPromptBuilder
from skiller.application.agent.runner_state import AgentRunnerState
from skiller.domain.agent.agent_context_model import (
    AgentContextEntry,
    AgentContextEntryType,
    AgentUserMessagePayload,
)
from skiller.domain.agent.agent_run_scope import AgentRunScope
from skiller.domain.tool.tool_contract import ToolConfig

pytestmark = pytest.mark.unit


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
    state = AgentRunnerState(
        run_id="run-1",
        agent_id="agent-1",
        context_id="ctx-1",
        config=agent_runner_config(
            task="Task",
            system="Be useful.",
            context_id="ctx-1",
            max_turns=1,
            tools=["notify"],
        ),
        enabled_tools=[
            ToolConfig(
                name="notify",
                description="Send notification",
                parameters_schema={"type": "object", "properties": {}},
            )
        ],
    )

    result = manager.build_llm_request(state=state)

    assert result.turn_id == "turn-2"
    assert [message.role.value for message in result.llm_request.messages] == [
        "system",
        "user",
    ]
    assert result.llm_request.messages[0].content == "Be useful."
    assert result.llm_request.messages[1].content == "Hello"
    assert [tool.name for tool in result.llm_request.tools] == ["notify"]


class _FakeAgentContextStore:
    def __init__(
        self,
        *,
        entries: list[AgentContextEntry],
        next_turn_id: str,
    ) -> None:
        self.entries = entries
        self.next = next_turn_id

    def init_db(self) -> None:
        raise NotImplementedError

    def append_user_message(self, **kwargs):  # noqa: ANN003, ANN201
        raise NotImplementedError

    def append_assistant_message(self, **kwargs):  # noqa: ANN003, ANN201
        raise NotImplementedError

    def append_tool_call(self, **kwargs):  # noqa: ANN003, ANN201
        raise NotImplementedError

    def append_tool_result(self, **kwargs):  # noqa: ANN003, ANN201
        raise NotImplementedError

    def list_entries(self, *, scope: AgentRunScope) -> list[AgentContextEntry]:
        _ = scope
        return self.entries

    def next_turn_id(self, *, scope: AgentRunScope) -> str:
        _ = scope
        return self.next
