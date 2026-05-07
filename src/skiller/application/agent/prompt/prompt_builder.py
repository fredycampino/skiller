import json
from dataclasses import dataclass, field
from typing import Any

from skiller.application.ports.llm.llm_port import (
    LLMMessage,
    LLMToolCall,
    LLMToolCallFunction,
)
from skiller.domain.agent.agent_context_model import AgentContextEntry, AgentContextEntryType


class AgentPromptBuilder:
    def build_messages(
        self,
        *,
        system: str,
        entries: list[AgentContextEntry],
    ) -> list[LLMMessage]:
        messages = [LLMMessage.system(system)]
        pending_turn: _PendingAssistantTurn | None = None
        tool_call_ids_by_turn_id: dict[str, list[str]] = {}

        def flush_pending_turn() -> None:
            nonlocal pending_turn
            if pending_turn is None:
                return
            messages.append(
                LLMMessage.assistant(
                    pending_turn.content,
                    tool_calls=tuple(pending_turn.tool_calls),
                )
            )
            messages.extend(pending_turn.tool_results)
            pending_turn = None

        for entry in entries:
            turn_id = self._entry_turn_id(entry)
            if entry.entry_type == AgentContextEntryType.USER_MESSAGE:
                flush_pending_turn()
                text = str(entry.payload.get("text", ""))
                if text:
                    messages.append(LLMMessage.user(text))
                continue
            if entry.entry_type == AgentContextEntryType.ASSISTANT_MESSAGE:
                text = str(entry.payload.get("text", ""))
                if pending_turn is None or pending_turn.turn_id != turn_id:
                    flush_pending_turn()
                    pending_turn = _PendingAssistantTurn(turn_id=turn_id)
                if text:
                    pending_turn.content = text
                continue
            if entry.entry_type == AgentContextEntryType.TOOL_CALL:
                if pending_turn is None or pending_turn.turn_id != turn_id:
                    flush_pending_turn()
                    pending_turn = _PendingAssistantTurn(turn_id=turn_id)
                tool_call = self._build_tool_call(entry)
                pending_turn.tool_calls.append(tool_call)
                tool_call_ids_by_turn_id.setdefault(turn_id, []).append(tool_call.id)
                continue
            if entry.entry_type == AgentContextEntryType.TOOL_RESULT:
                if pending_turn is None or pending_turn.turn_id != turn_id:
                    flush_pending_turn()
                    pending_turn = _PendingAssistantTurn(turn_id=turn_id)
                tool_call_id = self._tool_call_id_for_result(
                    entry,
                    turn_id=turn_id,
                    tool_call_ids_by_turn_id=tool_call_ids_by_turn_id,
                )
                pending_turn.tool_results.append(
                    LLMMessage.tool(
                        self._tool_result_content(entry.payload),
                        tool_call_id=tool_call_id,
                    )
                )
                continue

        flush_pending_turn()
        return messages

    def _build_tool_call(self, entry: AgentContextEntry) -> LLMToolCall:
        tool_name = str(entry.payload.get("tool", "")).strip()
        args = entry.payload.get("args")
        arguments_json = json.dumps(
            args if isinstance(args, dict) else {},
            ensure_ascii=False,
            sort_keys=True,
        )
        return LLMToolCall(
            id=self._tool_call_id_for_entry(entry),
            function=LLMToolCallFunction(
                name=tool_name,
                arguments_json=arguments_json,
            ),
        )

    def _tool_call_id_for_entry(self, entry: AgentContextEntry) -> str:
        raw_tool_call_id = str(entry.payload.get("tool_call_id", "")).strip()
        if raw_tool_call_id:
            return raw_tool_call_id
        return entry.id

    def _tool_call_id_for_result(
        self,
        entry: AgentContextEntry,
        *,
        turn_id: str,
        tool_call_ids_by_turn_id: dict[str, list[str]],
    ) -> str:
        raw_tool_call_id = str(entry.payload.get("tool_call_id", "")).strip()
        if raw_tool_call_id:
            return raw_tool_call_id
        turn_tool_call_ids = tool_call_ids_by_turn_id.get(turn_id)
        if turn_tool_call_ids:
            return turn_tool_call_ids[0]
        return entry.id

    def _tool_result_content(self, payload: dict[str, Any]) -> str:
        text = payload.get("text")
        if isinstance(text, str) and text:
            return text

        data = payload.get("data")
        if data is not None:
            return json.dumps(data, ensure_ascii=False, sort_keys=True)

        error = payload.get("error")
        if error is not None:
            return str(error)

        return ""

    def _entry_turn_id(self, entry: AgentContextEntry) -> str:
        return str(entry.payload.get("turn_id", "")).strip()


@dataclass
class _PendingAssistantTurn:
    turn_id: str
    content: str | None = None
    tool_calls: list[LLMToolCall] = field(default_factory=list)
    tool_results: list[LLMMessage] = field(default_factory=list)
