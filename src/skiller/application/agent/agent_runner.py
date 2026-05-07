from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from skiller.application.agent.config.event_output_sanitizer import (
    AgentEventOutputSanitizer,
)
from skiller.application.agent.config.step_config_reader import AgentStepConfig
from skiller.application.agent.observer.runtime_event_emitter import AgentRuntimeEventEmitter
from skiller.application.agent.prompt.final_message_extractor import (
    AgentFinalMessageExtractor,
)
from skiller.application.agent.prompt.prompt_builder import AgentPromptBuilder
from skiller.application.agent.tools.tool_manager import ToolManager
from skiller.application.agent.tools.tool_turn_executor import (
    AgentToolTurnExecutor,
)
from skiller.application.agent.tools.tool_turn_executor_model import (
    AgentTurnLoop,
    ToolTurnRequest,
)
from skiller.application.ports.agent.agent_context_store_port import AgentContextStorePort
from skiller.application.ports.agent.agent_steering_port import AgentSteeringPort
from skiller.application.ports.llm.llm_port import LLMPort, LLMRequest
from skiller.domain.agent.agent_context_model import (
    AgentContextEntry,
    AgentContextEntryType,
)
from skiller.domain.tool.tool_contract import ToolConfig


@dataclass(frozen=True)
class AgentRunnerRequest:
    run_id: str
    step_id: str
    config: AgentStepConfig


@dataclass(frozen=True)
class AgentRunnerResult:
    final_text: str
    turn_count: int
    tool_call_count: int
    stop_reason: str
    response_model: str | None


class AgentRunner:
    def __init__(
        self,
        *,
        agent_context_store: AgentContextStorePort,
        agent_steering: AgentSteeringPort,
        llm: LLMPort,
        tool_manager: ToolManager | None,
        prompt_builder: AgentPromptBuilder,
        final_message_extractor: AgentFinalMessageExtractor,
        event_output_sanitizer: AgentEventOutputSanitizer,
        event_emitter: AgentRuntimeEventEmitter,
        tool_turn_executor: AgentToolTurnExecutor,
    ) -> None:
        self.agent_context_store = agent_context_store
        self.agent_steering = agent_steering
        self.llm = llm
        self.tool_manager = tool_manager
        self.prompt_builder = prompt_builder
        self.final_message_extractor = final_message_extractor
        self.event_output_sanitizer = event_output_sanitizer
        self.event_emitter = event_emitter
        self.tool_turn_executor = tool_turn_executor

    def execute(self, request: AgentRunnerRequest) -> AgentRunnerResult:
        config = request.config
        step_id = request.step_id
        run_id = request.run_id

        enabled_tools = self._get_enabled_tool_configs(step_id=step_id, tools=config.tools)
        self._append_initial_user_task(
            run_id=run_id,
            step_id=step_id,
            config=config,
        )

        turn_loop = AgentTurnLoop(max_turns=config.max_turns)
        tool_call_count = 0
        final_text: str | None = None
        stop_reason: str | None = None
        response_model: str | None = None

        while turn_loop.has_next():
            self._append_last_turn_warning_if_needed(
                run_id=run_id,
                step_id=step_id,
                context_id=config.context_id,
                tools_enabled=bool(config.tools),
                turn_loop=turn_loop,
            )
            entries = self.agent_context_store.list_entries(
                run_id=run_id,
                context_id=config.context_id,
            )
            turn_id = self._next_turn_id(entries)
            response = self.llm.generate(
                self._build_llm_request(
                    config=config,
                    entries=entries,
                    enabled_tools=enabled_tools,
                    turn_loop=turn_loop,
                )
            )
            self._raise_if_failed(step_id=step_id, response=response)
            response_model = str(response.model or "").strip() or None

            if not config.tools:
                final_text = self._append_final_assistant_message(
                    run_id=run_id,
                    step_id=step_id,
                    context_id=config.context_id,
                    turn_id=turn_id,
                    content=response.content,
                )
                turn_loop.advance()
                stop_reason = "final"
                break

            tool_turn_results = self.tool_turn_executor.execute(
                ToolTurnRequest(
                    run_id=run_id,
                    step_id=step_id,
                    context_id=config.context_id,
                    turn_id=turn_id,
                    response=response,
                    allowed_tools=config.tools,
                    max_tool_calls=config.max_tool_calls,
                    turn_loop=turn_loop,
                )
            )
            tool_call_count += tool_turn_results.executed_count()
            tool_turn_outcome = self._resolve_tool_turn_outcome(
                tool_turn_results=tool_turn_results,
            )
            if tool_turn_outcome is None:
                continue
            stop_reason = tool_turn_outcome
            if stop_reason == "success":
                final_text = self._append_final_assistant_message(
                    run_id=run_id,
                    step_id=step_id,
                    context_id=config.context_id,
                    turn_id=turn_id,
                    content=response.content,
                )
                turn_loop.advance()
                break
            if stop_reason == "interrupted":
                final_text = self._append_fixed_final_assistant_message(
                    run_id=run_id,
                    step_id=step_id,
                    context_id=config.context_id,
                    turn_id=self._next_turn_id(
                        self.agent_context_store.list_entries(
                            run_id=run_id,
                            context_id=config.context_id,
                        )
                    ),
                    text="Interrupted. Send another message if you want to continue.",
                )
            break

        if final_text is None:
            final_text, stop_reason = self._handle_max_turns_exhausted(
                run_id=run_id,
                step_id=step_id,
                context_id=config.context_id,
            )

        return AgentRunnerResult(
            final_text=final_text,
            turn_count=turn_loop.turn_count,
            tool_call_count=tool_call_count,
            stop_reason=stop_reason or "final",
            response_model=response_model,
        )

    def _next_turn_number(self, entries: list[AgentContextEntry]) -> int:
        llm_turn_count = sum(
            1
            for entry in entries
            if entry.entry_type
            in {
                AgentContextEntryType.ASSISTANT_MESSAGE,
                AgentContextEntryType.TOOL_CALL,
            }
        )
        return llm_turn_count + 1

    def _next_turn_id(self, entries: list[AgentContextEntry]) -> str:
        return f"turn-{self._next_turn_number(entries)}"

    def _append_initial_user_task(
        self,
        *,
        run_id: str,
        step_id: str,
        config: AgentStepConfig,
    ) -> None:
        existing_entries = self.agent_context_store.list_entries(
            run_id=run_id,
            context_id=config.context_id,
        )
        self.agent_context_store.append_user_message(
            run_id=run_id,
            context_id=config.context_id,
            source_step_id=step_id,
            turn_id=self._next_turn_id(existing_entries),
            text=config.task,
        )

    def _build_llm_request(
        self,
        *,
        config: AgentStepConfig,
        entries: list[AgentContextEntry],
        enabled_tools: list[ToolConfig],
        turn_loop: AgentTurnLoop,
    ) -> LLMRequest:
        prompt_messages = self.prompt_builder.build_messages(
            system=config.system,
            entries=entries,
        )
        return LLMRequest(
            messages=tuple(prompt_messages),
            tools=tuple(enabled_tools),
        )

    def _append_final_assistant_message(
        self,
        *,
        run_id: str,
        step_id: str,
        context_id: str,
        turn_id: str,
        content: str | None,
    ) -> str:
        final_text = self.final_message_extractor.extract_final_message(
            step_id=step_id,
            content=content,
        )
        assistant_message_entry = self.agent_context_store.append_assistant_message(
            run_id=run_id,
            context_id=context_id,
            source_step_id=step_id,
            turn_id=turn_id,
            message_type="final",
            text=final_text,
        )
        self.event_emitter.emit_assistant_message(
            run_id=run_id,
            step_id=step_id,
            turn_id=turn_id,
            sequence=assistant_message_entry.sequence,
            message_type="final",
            text=self._sanitize_assistant_text(final_text),
        )
        return final_text

    def _resolve_tool_turn_outcome(
        self,
        *,
        tool_turn_results,
    ) -> str | None:
        if tool_turn_results.is_interrupted():
            return "interrupted"
        if tool_turn_results.items:
            return None
        return "success"

    def _handle_max_turns_exhausted(
        self,
        *,
        run_id: str,
        step_id: str,
        context_id: str,
    ) -> tuple[str, str]:
        entries = self.agent_context_store.list_entries(
            run_id=run_id,
            context_id=context_id,
        )
        self.agent_context_store.append_user_message(
            run_id=run_id,
            context_id=context_id,
            source_step_id=step_id,
            turn_id=self._next_turn_id(entries),
            text=(
                "Agent reached max_turns without producing a final answer. "
                "Ask the user whether to continue."
            ),
        )
        final_text = self._append_fixed_final_assistant_message(
            run_id=run_id,
            step_id=step_id,
            context_id=context_id,
            turn_id=self._next_turn_id(
                self.agent_context_store.list_entries(
                    run_id=run_id,
                    context_id=context_id,
                )
            ),
            text=(
                "I reached the turn limit before finishing. "
                "Send another message if you want me to continue."
            ),
        )
        return final_text, "max_turns_exhausted"

    def _raise_if_failed(self, *, step_id: str, response: Any) -> None:
        if response.ok is False:
            error = str(response.error or "").strip() or f"Agent step '{step_id}' failed"
            raise ValueError(error)

    def _sanitize_assistant_text(self, text: str) -> str:
        sanitized = self.event_output_sanitizer.sanitize_output(
            {"text": text, "value": None, "body_ref": None}
        )
        return str(sanitized.get("text", ""))

    def _append_fixed_final_assistant_message(
        self,
        *,
        run_id: str,
        step_id: str,
        context_id: str,
        turn_id: str,
        text: str,
    ) -> str:
        assistant_message_entry = self.agent_context_store.append_assistant_message(
            run_id=run_id,
            context_id=context_id,
            source_step_id=step_id,
            turn_id=turn_id,
            message_type="final",
            text=text,
        )
        self.event_emitter.emit_assistant_message(
            run_id=run_id,
            step_id=step_id,
            turn_id=turn_id,
            sequence=assistant_message_entry.sequence,
            message_type="final",
            text=self._sanitize_assistant_text(text),
        )
        return text

    def _append_last_turn_warning_if_needed(
        self,
        *,
        run_id: str,
        step_id: str,
        context_id: str,
        tools_enabled: bool,
        turn_loop: AgentTurnLoop,
    ) -> None:
        if not tools_enabled:
            return
        remaining_turns = turn_loop.max_turns - turn_loop.turn_count
        if remaining_turns != 1:
            return
        entries = self.agent_context_store.list_entries(
            run_id=run_id,
            context_id=context_id,
        )
        warning = (
            "Skiller warning: this is the last allowed turn. "
            "If you can finish, return the best final answer now. "
            "Otherwise, ask the user whether to continue. "
            "Do not plan more follow-up turns."
        )
        if any(
            entry.entry_type == AgentContextEntryType.USER_MESSAGE
            and entry.source_step_id == step_id
            and entry.payload.get("text") == warning
            for entry in entries
        ):
            return
        self.agent_context_store.append_user_message(
            run_id=run_id,
            context_id=context_id,
            source_step_id=step_id,
            turn_id=self._next_turn_id(entries),
            text=warning,
        )

    def _get_enabled_tool_configs(
        self,
        *,
        step_id: str,
        tools: list[str],
    ) -> list[ToolConfig]:
        if not tools:
            return []
        if self.tool_manager is None:
            raise ValueError(f"Step '{step_id}' requires tool_manager for tools")
        return self.tool_manager.get_tool_configs(tools)
