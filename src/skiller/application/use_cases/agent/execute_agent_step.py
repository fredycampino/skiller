import json
import re
from dataclasses import dataclass
from typing import Any

from skiller.application.ports.agent_context_store_port import AgentContextStorePort
from skiller.application.ports.llm_port import LLMPort
from skiller.application.ports.run_store_port import RunStorePort
from skiller.application.use_cases.agent.tool_manager import ToolManager
from skiller.application.use_cases.agent.tool_manager_model import AgentToolRequest
from skiller.application.use_cases.render.render_current_step import CurrentStep
from skiller.application.use_cases.shared.step_execution_result import (
    StepAdvance,
    StepExecutionStatus,
)
from skiller.domain.agent.agent_context_model import AgentContextEntry, AgentContextEntryType
from skiller.domain.run.run_model import RunStatus
from skiller.domain.step.step_execution_model import AgentOutput, StepExecution
from skiller.domain.tool.tool_contract import ToolResult

_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)
_JSON_QUOTED_BLOCK_RE = re.compile(
    r'^\s*(?:\'\'\'|""")\s*(?:json)?\s*(.*?)\s*(?:\'\'\'|""")\s*$',
    re.DOTALL | re.IGNORECASE,
)


@dataclass(frozen=True)
class _AgentStepConfig:
    system: str
    task: str
    context_id: str
    max_turns: int
    tools: list[str]


@dataclass(frozen=True)
class _AgentTurnDecision:
    type: str
    text: str | None = None
    tool: str | None = None
    args: dict[str, Any] | None = None


class ExecuteAgentStepUseCase:
    def __init__(
        self,
        store: RunStorePort,
        agent_context_store: AgentContextStorePort,
        llm: LLMPort,
        tool_manager: ToolManager | None = None,
    ) -> None:
        self.store = store
        self.agent_context_store = agent_context_store
        self.llm = llm
        self.tool_manager = tool_manager

    def execute(self, current_step: CurrentStep) -> StepAdvance:
        step_id = current_step.step_id
        config = self._read_step_config(
            step_id=step_id,
            run_id=current_step.run_id,
            step=current_step.step,
        )
        enabled_tools = self._get_enabled_tools(step_id=step_id, tools=config.tools)
        existing_entries = self.agent_context_store.list_entries(
            run_id=current_step.run_id,
            context_id=config.context_id,
        )

        self.agent_context_store.append_entry(
            run_id=current_step.run_id,
            context_id=config.context_id,
            entry_type=AgentContextEntryType.USER_MESSAGE,
            payload={"type": "user_message", "text": config.task},
            source_step_id=step_id,
            idempotency_key=f"user:{step_id}:{self._next_turn_id(existing_entries)}",
        )
        turn_count = 0
        tool_call_count = 0
        final_text: str | None = None
        stop_reason: str | None = None
        response_model: str | None = None

        while turn_count < config.max_turns:
            entries = self.agent_context_store.list_entries(
                run_id=current_step.run_id,
                context_id=config.context_id,
            )
            turn_id = self._next_turn_id(entries)
            messages = self._build_messages(
                system=self._build_effective_system(
                    system=config.system,
                    enabled_tools=enabled_tools,
                ),
                entries=entries,
            )
            response = self.llm.generate(
                messages,
                config=self._build_llm_config(
                    step_id=step_id,
                    max_turns=config.max_turns,
                    enabled_tools=enabled_tools,
                ),
            )
            self._raise_if_failed(step_id=step_id, response=response)
            response_model = str(response.get("model", "")).strip() or None

            if not config.tools:
                final_text = self._extract_final_text(step_id=step_id, response=response)
                if not final_text.strip():
                    raise ValueError(f"Agent step '{step_id}' did not produce a final answer")

                self.agent_context_store.append_entry(
                    run_id=current_step.run_id,
                    context_id=config.context_id,
                    entry_type=AgentContextEntryType.ASSISTANT_MESSAGE,
                    payload={"type": "assistant_message", "turn_id": turn_id, "text": final_text},
                    source_step_id=step_id,
                    idempotency_key=f"final:{step_id}:{turn_id}",
                )
                turn_count += 1
                stop_reason = "final"
                break

            try:
                decision = self._try_extract_tool_decision(step_id=step_id, response=response)
            except ValueError as exc:
                raise ValueError(
                    self._build_invalid_decision_error(
                        step_id=step_id,
                        response=response,
                        error=exc,
                    )
                ) from exc

            if decision is None:
                final_text = self._extract_final_text(step_id=step_id, response=response)
                if not final_text.strip():
                    raise ValueError(f"Agent step '{step_id}' did not produce a final answer")
                self.agent_context_store.append_entry(
                    run_id=current_step.run_id,
                    context_id=config.context_id,
                    entry_type=AgentContextEntryType.ASSISTANT_MESSAGE,
                    payload={"type": "assistant_message", "turn_id": turn_id, "text": final_text},
                    source_step_id=step_id,
                    idempotency_key=f"final:{step_id}:{turn_id}",
                )
                turn_count += 1
                stop_reason = "success"
                break

            self.agent_context_store.append_entry(
                run_id=current_step.run_id,
                context_id=config.context_id,
                entry_type=AgentContextEntryType.TOOL_CALL,
                payload={
                    "type": "tool_call",
                    "turn_id": turn_id,
                    "tool": decision.tool,
                    "args": decision.args or {},
                },
                source_step_id=step_id,
                idempotency_key=f"tool_call:{step_id}:{turn_id}",
            )
            tool_result = self._execute_tool(
                run_id=current_step.run_id,
                step_id=step_id,
                context_id=config.context_id,
                turn_id=turn_id,
                tool=decision.tool,
                args=decision.args or {},
                allowed_tools=config.tools,
            )
            self.agent_context_store.append_entry(
                run_id=current_step.run_id,
                context_id=config.context_id,
                entry_type=AgentContextEntryType.TOOL_RESULT,
                payload={
                    "type": "tool_result",
                    "turn_id": turn_id,
                    "tool": tool_result.name,
                    "status": tool_result.status.value,
                    "data": tool_result.data,
                    "text": tool_result.text,
                    "error": tool_result.error,
                },
                source_step_id=step_id,
                idempotency_key=f"tool_result:{step_id}:{turn_id}",
            )
            turn_count += 1
            tool_call_count += 1

        if final_text is None:
            raise ValueError(
                f"Agent step '{step_id}' reached max_turns before producing a final answer"
            )

        output_data = {
            "context_id": config.context_id,
            "final": {"text": final_text},
            "turn_count": turn_count,
            "tool_call_count": tool_call_count,
            "stop_reason": stop_reason or "final",
        }
        execution = StepExecution(
            step_type=current_step.step_type,
            input={
                "system": config.system,
                "task": config.task,
                "context_id": config.context_id,
                "max_turns": config.max_turns,
                "tools": list(config.tools),
            },
            evaluation={"model": response_model},
            output=AgentOutput(
                text=final_text,
                text_ref="data.final.text",
                data=output_data,
            ),
        )
        current_step.context.step_executions[step_id] = execution
        return self._advance(current_step=current_step, execution=execution)

    def _read_step_config(
        self,
        *,
        step_id: str,
        run_id: str,
        step: dict[str, Any],
    ) -> _AgentStepConfig:
        system = str(step.get("system", ""))
        if not system.strip():
            raise ValueError(f"Step '{step_id}' requires system")

        task = str(step.get("task", ""))
        if not task.strip():
            raise ValueError(f"Step '{step_id}' requires task")

        raw_context_id = step.get("context_id")
        context_id = str(raw_context_id).strip() if raw_context_id is not None else run_id
        if not context_id:
            raise ValueError(f"Step '{step_id}' requires non-empty context_id")

        max_turns = self._parse_max_turns(step_id=step_id, value=step.get("max_turns"))
        tools = self._parse_tools(step_id=step_id, value=step.get("tools"))

        return _AgentStepConfig(
            system=system,
            task=task,
            context_id=context_id,
            max_turns=max_turns,
            tools=tools,
        )

    def _parse_max_turns(self, *, step_id: str, value: object) -> int:
        if value is None:
            return 1
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"Step '{step_id}' requires integer max_turns")
        if value <= 0:
            raise ValueError(f"Step '{step_id}' requires positive max_turns")
        return value

    def _parse_tools(self, *, step_id: str, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError(f"Step '{step_id}' requires list tools")
        tools: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"Step '{step_id}' requires non-empty tool names")
            tools.append(item.strip())
        return tools

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

    def _build_messages(
        self,
        *,
        system: str,
        entries: list[AgentContextEntry],
    ) -> list[dict[str, str]]:
        messages = [{"role": "system", "content": system}]
        for entry in entries:
            if entry.entry_type == AgentContextEntryType.USER_MESSAGE:
                text = str(entry.payload.get("text", ""))
                if text:
                    messages.append({"role": "user", "content": text})
                continue
            if entry.entry_type == AgentContextEntryType.ASSISTANT_MESSAGE:
                text = str(entry.payload.get("text", ""))
                if text:
                    messages.append({"role": "assistant", "content": text})
                continue
            if entry.entry_type == AgentContextEntryType.TOOL_CALL:
                messages.append(
                    {
                        "role": "assistant",
                        "content": self._serialize_entry_payload(entry.payload),
                    }
                )
                continue
            if entry.entry_type == AgentContextEntryType.TOOL_RESULT:
                messages.append(
                    {
                        "role": "user",
                        "content": self._serialize_entry_payload(entry.payload),
                    }
                )
        return messages

    def _build_effective_system(
        self,
        *,
        system: str,
        enabled_tools: list[Any],
    ) -> str:
        if not enabled_tools:
            return system

        tool_names = [tool.name for tool in enabled_tools]
        tool_list = ", ".join(tool_names)
        tool_names_json = json.dumps(tool_names, ensure_ascii=False)
        return (
            f"{system.rstrip()}\n\n"
            "If you need to use a tool, reply with exactly one JSON object and no extra text.\n"
            'The only structured tool response type is "tool_call".\n'
            f"Allowed tools are: {tool_list}.\n"
            f'Use only tool names from this list: {tool_names_json}.\n'
            'For a tool call respond with {"type":"tool_call","tool":"<tool>","args":{...}}.\n'
            'Example tool call: {"type":"tool_call","tool":"shell",'
            '"args":{"command":"pytest -q"}}.\n'
            "When the task is complete, answer the user directly in plain text.\n"
            "Do not wrap the final answer in JSON unless you are making a tool call.\n"
            "If a tool fails, use the returned tool_result to decide whether to try another "
            "tool or continue reasoning. "
            "Do not emit an error terminal response."
        )

    def _serialize_entry_payload(self, payload: dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    def _raise_if_failed(self, *, step_id: str, response: dict[str, Any]) -> None:
        if response.get("ok") is False:
            error = str(response.get("error", "")).strip() or f"Agent step '{step_id}' failed"
            raise ValueError(error)

    def _extract_final_text(self, *, step_id: str, response: dict[str, Any]) -> str:
        if "json" in response:
            return self._text_from_value(response["json"])

        content = response.get("content")
        if isinstance(content, str):
            parsed = self._try_parse_json(content)
            if parsed is not None:
                return self._text_from_value(parsed)
            return content

        if isinstance(content, (dict, list, int, float, bool)) or content is None:
            return self._text_from_value(content)

        raise ValueError(f"Agent step '{step_id}' returned invalid response payload")

    def _text_from_value(self, value: Any) -> str:
        if isinstance(value, dict):
            if isinstance(value.get("text"), str):
                return str(value["text"])
            if isinstance(value.get("reply"), str):
                return str(value["reply"])
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        if isinstance(value, list):
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        if value is None:
            return ""
        return str(value)

    def _try_parse_json(self, content: str) -> Any:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            normalized = self._strip_json_wrappers(content)
            if normalized != content:
                try:
                    return json.loads(normalized)
                except json.JSONDecodeError:
                    pass

            candidate = self._extract_json_candidate(normalized)
            if candidate is None:
                return None
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                return None

    def _strip_json_wrappers(self, content: str) -> str:
        normalized = content.strip()
        previous = ""

        while normalized != previous:
            previous = normalized

            fenced = self._strip_json_fence(normalized)
            if fenced != normalized:
                normalized = fenced.strip()
                continue

            quoted = self._strip_json_quoted_block(normalized)
            if quoted != normalized:
                normalized = quoted.strip()

        return normalized

    def _strip_json_fence(self, content: str) -> str:
        match = _JSON_FENCE_RE.match(content)
        if match is None:
            return content
        return match.group(1).strip()

    def _strip_json_quoted_block(self, content: str) -> str:
        match = _JSON_QUOTED_BLOCK_RE.match(content)
        if match is None:
            return content
        return match.group(1).strip()

    def _extract_json_candidate(self, content: str) -> str | None:
        object_start = content.find("{")
        object_end = content.rfind("}")
        if object_start >= 0 and object_end > object_start:
            return content[object_start : object_end + 1]

        array_start = content.find("[")
        array_end = content.rfind("]")
        if array_start >= 0 and array_end > array_start:
            return content[array_start : array_end + 1]

        return None

    def _try_extract_tool_decision(
        self,
        *,
        step_id: str,
        response: dict[str, Any],
    ) -> _AgentTurnDecision | None:
        parsed = self._extract_json_candidate_value(response=response)
        if not isinstance(parsed, dict):
            return None

        decision_type = str(parsed.get("type", "")).strip()
        if decision_type == "success":
            return None

        if decision_type == "tool_call":
            raw_tool = parsed.get("tool")
            if not isinstance(raw_tool, str) or not raw_tool.strip():
                raise ValueError(f"Agent step '{step_id}' returned tool_call without tool")
            tool = raw_tool.strip()
            raw_args = parsed.get("args")
            args = raw_args if isinstance(raw_args, dict) else {}
            return _AgentTurnDecision(type="tool_call", tool=tool, args=args)

        return None

    def _extract_json_candidate_value(self, *, response: dict[str, Any]) -> Any:
        if "json" in response:
            return response["json"]

        content = response.get("content")
        if isinstance(content, str):
            return self._try_parse_json(content)

        if isinstance(content, (dict, list, int, float, bool)) or content is None:
            return content

        return None

    def _extract_json_value(self, *, step_id: str, response: dict[str, Any]) -> Any:
        if "json" in response:
            return response["json"]

        content = response.get("content")
        if isinstance(content, str):
            parsed = self._try_parse_json(content)
            if parsed is None:
                raise ValueError(f"Agent step '{step_id}' returned invalid JSON decision")
            return parsed

        if isinstance(content, (dict, list, int, float, bool)) or content is None:
            return content

        raise ValueError(f"Agent step '{step_id}' returned invalid response payload")

    def _build_invalid_decision_error(
        self,
        *,
        step_id: str,
        response: dict[str, Any],
        error: ValueError,
    ) -> str:
        detail = str(error).strip() or f"Agent step '{step_id}' returned invalid JSON decision"
        excerpt = self._response_excerpt(response)
        if excerpt is None:
            return detail
        return f"{detail}. Raw response: {excerpt}"

    def _response_excerpt(self, response: dict[str, Any]) -> str | None:
        if "json" in response:
            try:
                serialized = json.dumps(response["json"], ensure_ascii=False, sort_keys=True)
            except TypeError:
                serialized = str(response["json"])
            return self._truncate_excerpt(serialized)

        content = response.get("content")
        if content is None:
            return None
        if isinstance(content, str):
            return self._truncate_excerpt(content)
        if isinstance(content, (dict, list, int, float, bool)):
            try:
                serialized = json.dumps(content, ensure_ascii=False, sort_keys=True)
            except TypeError:
                serialized = str(content)
            return self._truncate_excerpt(serialized)
        return self._truncate_excerpt(str(content))

    def _truncate_excerpt(self, content: str, *, limit: int = 280) -> str:
        normalized = " ".join(content.split())
        if len(normalized) <= limit:
            return normalized
        return f"{normalized[:limit].rstrip()}..."

    def _get_enabled_tools(
        self,
        *,
        step_id: str,
        tools: list[str],
    ) -> list[Any]:
        if not tools:
            return []
        if self.tool_manager is None:
            raise ValueError(f"Step '{step_id}' requires tool_manager for tools")
        return self.tool_manager.get_tools(tools)

    def _execute_tool(
        self,
        *,
        run_id: str,
        step_id: str,
        context_id: str,
        turn_id: str,
        tool: str,
        args: dict[str, Any],
        allowed_tools: list[str],
    ) -> ToolResult:
        if self.tool_manager is None:
            raise ValueError(f"Step '{step_id}' requires tool_manager for tools")
        return self.tool_manager.execute(
            AgentToolRequest(
                run_id=run_id,
                step_id=step_id,
                context_id=context_id,
                turn_id=turn_id,
                tool=tool,
                args=args,
                allowed_tools=allowed_tools,
            )
        )

    def _build_llm_config(
        self,
        *,
        step_id: str,
        max_turns: int,
        enabled_tools: list[Any],
    ) -> dict[str, Any]:
        config: dict[str, Any] = {
            "step_id": step_id,
            "agent": True,
            "max_turns": max_turns,
        }
        if enabled_tools:
            config["tools"] = [tool.name for tool in enabled_tools]
        return config

    def _advance(self, *, current_step: CurrentStep, execution: StepExecution) -> StepAdvance:
        step_id = current_step.step_id
        raw_next = current_step.step.get("next")

        if raw_next is None:
            self.store.update_run(
                current_step.run_id,
                status=RunStatus.RUNNING,
                context=current_step.context,
            )
            return StepAdvance(
                status=StepExecutionStatus.COMPLETED,
                execution=execution,
            )

        next_step_id = str(raw_next).strip()
        if not next_step_id:
            raise ValueError(f"Step '{step_id}' requires non-empty next")

        self.store.update_run(
            current_step.run_id,
            status=RunStatus.RUNNING,
            current=next_step_id,
            context=current_step.context,
        )
        return StepAdvance(
            status=StepExecutionStatus.NEXT,
            next_step_id=next_step_id,
            execution=execution,
        )
