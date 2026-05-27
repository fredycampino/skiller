import json
from dataclasses import dataclass, field

from skiller.domain.agent.agent_context_model import (
    AgentAssistantMessagePayload,
    AgentContextEntry,
    AgentToolCallPayload,
    AgentToolResultPayload,
    AgentUserMessagePayload,
)
from skiller.domain.agent.llm_model import (
    LLMAssistantMessage,
    LLMMessage,
    LLMRequest,
    LLMSystemMessage,
    LLMToolCall,
    LLMToolCallFunction,
    LLMToolMessage,
    LLMUserMessage,
)
from skiller.domain.tool.tool_contract import ToolDefinition


class AgentPromptBuilder:
    def build_request(
        self,
        *,
        model: str,
        system: str,
        entries: list[AgentContextEntry],
        tools: tuple[ToolDefinition, ...],
    ) -> LLMRequest:
        return LLMRequest(
            messages=tuple(self._build_messages(system=system, entries=entries)),
            model=model,
            tools=tools,
        )

    def _build_messages(
        self,
        *,
        system: str,
        entries: list[AgentContextEntry],
    ) -> list[LLMMessage]:
        messages = [LLMSystemMessage(system)]
        pending_turn: _PendingAssistantTurn | None = None
        tool_call_ids_by_turn_id: dict[str, list[str]] = {}

        def flush_pending_turn() -> None:
            nonlocal pending_turn
            if pending_turn is None:
                return
            messages.append(
                LLMAssistantMessage(
                    pending_turn.content,
                    tool_calls=tuple(pending_turn.tool_calls),
                )
            )
            messages.extend(pending_turn.tool_results)
            pending_turn = None

        for entry in entries:
            turn_id = self._entry_turn_id(entry)
            if isinstance(entry.payload, AgentUserMessagePayload):
                flush_pending_turn()
                if entry.payload.text:
                    messages.append(LLMUserMessage(entry.payload.text))
                continue
            if isinstance(entry.payload, AgentAssistantMessagePayload):
                if pending_turn is None or pending_turn.turn_id != turn_id:
                    flush_pending_turn()
                    pending_turn = _PendingAssistantTurn(turn_id=turn_id)
                if entry.payload.text:
                    pending_turn.content = entry.payload.text
                continue
            if isinstance(entry.payload, AgentToolCallPayload):
                if pending_turn is None or pending_turn.turn_id != turn_id:
                    flush_pending_turn()
                    pending_turn = _PendingAssistantTurn(turn_id=turn_id)
                tool_call = self._build_tool_call(entry)
                pending_turn.tool_calls.append(tool_call)
                tool_call_ids_by_turn_id.setdefault(turn_id, []).append(tool_call.id)
                continue
            if isinstance(entry.payload, AgentToolResultPayload):
                if pending_turn is None or pending_turn.turn_id != turn_id:
                    flush_pending_turn()
                    pending_turn = _PendingAssistantTurn(turn_id=turn_id)
                tool_call_id = self._tool_call_id_for_result(
                    entry,
                    turn_id=turn_id,
                    tool_call_ids_by_turn_id=tool_call_ids_by_turn_id,
                )
                pending_turn.tool_results.append(
                    LLMToolMessage(
                        self._tool_result_content(entry.payload),
                        tool_call_id=tool_call_id,
                    )
                )
                continue

        flush_pending_turn()
        return messages

    def _build_tool_call(self, entry: AgentContextEntry) -> LLMToolCall:
        payload = entry.payload
        if not isinstance(payload, AgentToolCallPayload):
            raise ValueError("Tool call entry requires tool call payload")
        arguments_json = json.dumps(
            payload.args,
            ensure_ascii=False,
            sort_keys=True,
        )
        return LLMToolCall(
            id=self._tool_call_id_for_entry(entry),
            function=LLMToolCallFunction(
                name=payload.tool,
                arguments_json=arguments_json,
            ),
        )

    def _tool_call_id_for_entry(self, entry: AgentContextEntry) -> str:
        if isinstance(entry.payload, AgentToolCallPayload) and entry.payload.tool_call_id:
            return entry.payload.tool_call_id
        return entry.id

    def _tool_call_id_for_result(
        self,
        entry: AgentContextEntry,
        *,
        turn_id: str,
        tool_call_ids_by_turn_id: dict[str, list[str]],
    ) -> str:
        if isinstance(entry.payload, AgentToolResultPayload) and entry.payload.tool_call_id:
            return entry.payload.tool_call_id
        turn_tool_call_ids = tool_call_ids_by_turn_id.get(turn_id)
        if turn_tool_call_ids:
            return turn_tool_call_ids[0]
        return entry.id

    def _tool_result_content(self, payload: AgentToolResultPayload) -> str:
        if payload.text:
            return payload.text

        if payload.data:
            return json.dumps(payload.data, ensure_ascii=False, sort_keys=True)

        if payload.error is not None:
            return payload.error

        return ""

    def _entry_turn_id(self, entry: AgentContextEntry) -> str:
        if isinstance(entry.payload, AgentUserMessagePayload):
            return ""
        return entry.payload.turn_id


@dataclass
class _PendingAssistantTurn:
    turn_id: str
    content: str | None = None
    tool_calls: list[LLMToolCall] = field(default_factory=list)
    tool_results: list[LLMMessage] = field(default_factory=list)
