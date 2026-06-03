from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from skiller.application.agent.config.output_truncator import OutputTruncator
from skiller.domain.agent.agent_config_model import AgentEventOutputConfig
from skiller.domain.event.event_agent_model import (
    AgentEventPayload,
    AgentMessageEventBody,
    AgentToolCallEventBody,
    AgentToolResultEventBody,
)


@dataclass(frozen=True)
class AgentEventOutputPolicy:
    truncate_enabled: bool = True
    max_text_chars: int = 600
    max_json_chars: int = 4000
    max_array_items: int = 20

    @classmethod
    def from_config(cls, config: AgentEventOutputConfig) -> "AgentEventOutputPolicy":
        truncate = config.truncate
        return cls(
            truncate_enabled=truncate.enabled,
            max_text_chars=truncate.max_text_chars,
            max_json_chars=truncate.max_json_chars,
            max_array_items=truncate.max_array_items,
        )


class AgentEventTruncator:
    def __init__(
        self,
        policy: AgentEventOutputPolicy,
        output_truncator: OutputTruncator,
    ) -> None:
        self.policy = policy
        self.output_truncator = output_truncator

    def truncate_assistant_message(
        self,
        payload: AgentMessageEventBody,
    ) -> AgentMessageEventBody:
        return AgentMessageEventBody(
            total_tokens=payload.total_tokens,
            text=self._truncate_text(payload.text),
        )

    def truncate_tool_call(
        self,
        payload: AgentToolCallEventBody,
    ) -> AgentToolCallEventBody:
        return AgentToolCallEventBody(
            turn_id=payload.turn_id,
            parent_sequence=payload.parent_sequence,
            tool_call_id=payload.tool_call_id,
            tool=payload.tool,
            args=self._truncate_args(payload.args),
        )

    def truncate_tool_result(
        self,
        *,
        payload: AgentToolResultEventBody,
    ) -> AgentToolResultEventBody:
        truncated_data = self._truncate_value(payload.data)
        if isinstance(truncated_data, dict):
            data = self._truncate_json(truncated_data)
        else:
            data = self._truncate_json({})
        return AgentToolResultEventBody(
            turn_id=payload.turn_id,
            parent_sequence=payload.parent_sequence,
            tool_call_id=payload.tool_call_id,
            tool=payload.tool,
            status=payload.status,
            data=data,
            text=self._truncate_optional_text(payload.text),
            error=self._truncate_optional_text(payload.error),
        )

    def truncate_payload(self, payload: AgentEventPayload) -> AgentEventPayload:
        body = payload.body
        if isinstance(body, AgentMessageEventBody):
            body = self.truncate_assistant_message(body)
        if isinstance(body, AgentToolCallEventBody):
            body = self.truncate_tool_call(body)
        if isinstance(body, AgentToolResultEventBody):
            body = self.truncate_tool_result(payload=body)
        return AgentEventPayload(
            step_id=payload.step_id,
            turn_id=payload.turn_id,
            agent_sequence=payload.agent_sequence,
            body=body,
        )

    def _truncate_args(self, args: dict[str, object]) -> dict[str, object]:
        truncated = self._truncate_value(args)
        if isinstance(truncated, dict):
            return self._truncate_json(truncated)
        return self._truncate_json({})

    def _truncate_json(self, value: dict[str, Any]) -> dict[str, Any]:
        if not self.policy.truncate_enabled:
            return value
        truncated = self.output_truncator.cap_json_payload(
            value,
            max_chars=self.policy.max_json_chars,
        )
        if isinstance(truncated, dict):
            return truncated
        return {}

    def _truncate_optional_text(self, text: str | None) -> str | None:
        if text is None:
            return None
        return self._truncate_text(text)

    def _truncate_text(self, text: str) -> str:
        if not self.policy.truncate_enabled:
            return text
        return self.output_truncator.truncate_text(
            text,
            max_chars=self.policy.max_text_chars,
        )

    def _truncate_value(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                str(key): self._truncate_value(item)
                for key, item in value.items()
            }

        if isinstance(value, list):
            items = value
            if self.policy.truncate_enabled:
                items = self.output_truncator.truncate_list(
                    value,
                    max_items=self.policy.max_array_items,
                )
            return [self._truncate_value(item) for item in items]

        if isinstance(value, str):
            return self._truncate_text(value)

        return value
