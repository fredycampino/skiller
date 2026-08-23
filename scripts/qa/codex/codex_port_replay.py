#!/usr/bin/env python3
"""Replay a recorded Codex tool continuation through ``ResponsesLLMPort``.

This is the integrated counterpart to ``codex_stream_probe``. It reconstructs
the semantic request from a request log, sends a seed turn, then sends the
recorded tool results as a continuation through Skiller's real Codex port.
Only sanitized request/response metadata is written to the trace.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

try:
    from scripts.qa.codex.codex_stream_probe import (
        CodexProbeSource,
        load_probe_source,
    )
except ModuleNotFoundError:
    from codex_stream_probe import CodexProbeSource, load_probe_source

from skiller.domain.agent.llm.finish_type import LLMFinishType
from skiller.domain.agent.llm.model import (
    LLMAssistantMessage,
    LLMMessage,
    LLMSystemMessage,
    LLMToolCall,
    LLMToolCallFunction,
    LLMToolMessage,
    LLMUserMessage,
)
from skiller.domain.agent.llm.provider_catalog import LLMModelDefinition
from skiller.domain.agent.llm.provider_codex import CodexLLMRequest
from skiller.domain.tool.tool_contract import (
    ToolDefinition,
    ToolInput,
    ToolRequest,
    ToolRequestResult,
    ToolSchema,
)
from skiller.infrastructure.llm.codex.codex_credentials_datasource import (
    CodexCredentialsDatasource,
)
from skiller.infrastructure.llm.codex.codex_mapper import CodexMapper
from skiller.infrastructure.llm.codex.codex_model_capabilities import (
    CodexModelCapabilitiesResolver,
)
from skiller.infrastructure.llm.codex.codex_request_logger import (
    CODEX_TURN_STATE_HEADER,
)
from skiller.infrastructure.llm.codex.codex_turn_session import CodexTurnSessionManager
from skiller.infrastructure.llm.codex.collect_codex_response import CollectCodexResponse
from skiller.infrastructure.llm.codex.responses_general_mapper import ResponsesGeneralMapper
from skiller.infrastructure.llm.codex.responses_lite_mapper import ResponsesLiteMapper
from skiller.infrastructure.llm.codex.responses_llm_port import ResponsesLLMPort
from skiller.infrastructure.llm.codex.responses_mapper import ResponsesMapper
from skiller.infrastructure.llm.mapper.llm_usage_mapper import DefaultLLMUsageMapper


class _ReplayTool(ToolDefinition[ToolRequest]):
    def __init__(
        self,
        *,
        name: str,
        description: str,
        schema: Mapping[str, object],
    ) -> None:
        self.name = name
        self.description = description
        self._schema = ToolSchema(value=dict(schema))

    def schema(self) -> ToolSchema:
        return self._schema

    def request(self, input: ToolInput) -> ToolRequestResult[ToolRequest]:
        _ = input
        return ToolRequestResult.valid(ToolRequest())


class _TraceLogger:
    """Request logger that persists metadata without prompt or tool content."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._sequence = 0

    def log_request(
        self,
        *,
        request: object,
        file: Path,
        overwrite: bool | None = None,
    ) -> None:
        _ = file, overwrite
        self._sequence += 1
        self._write("request", sequence=self._sequence, summary=_request_summary(request))

    def log_response(self, *, response: object) -> None:
        self._write("response", summary=_response_summary(response))

    def log_error(self, *, error: str) -> None:
        self._write("error", error=error)

    def _write(self, event: str, **fields: object) -> None:
        record = {"event": event, **fields}
        with self.path.open("a", encoding="utf-8") as handle:
            json.dump(record, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")


def _request_summary(request: object) -> dict[str, object]:
    payload = _object_mapping(request)
    raw_input = payload.get("input")
    input_items = raw_input if isinstance(raw_input, list) else []
    input_types = Counter(_input_type(item) for item in input_items)
    extra_headers = payload.get("extra_headers")
    headers = extra_headers if isinstance(extra_headers, Mapping) else {}
    return {
        "model": payload.get("model"),
        "input_count": len(input_items),
        "input_types": dict(input_types),
        "parallel_tool_calls": payload.get("parallel_tool_calls"),
        "responses_lite": "x-openai-internal-codex-responses-lite" in headers,
        "turn_state_sent": CODEX_TURN_STATE_HEADER in headers,
        "header_names": sorted(str(name).lower() for name in headers),
        "has_reasoning": "reasoning" in payload,
    }


def _response_summary(response: object) -> dict[str, object]:
    raw_response = getattr(response, "response", response)
    payload = _object_mapping(raw_response)
    usage = _object_mapping(payload.get("usage"))
    output = payload.get("output")
    output_items = output if isinstance(output, list) else []
    return {
        "model": payload.get("model"),
        "status": payload.get("status"),
        "output_item_types": [_input_type(item) for item in output_items],
        "total_tokens": usage.get("total_tokens"),
    }


def _object_mapping(value: object) -> dict[str, object]:
    if isinstance(value, Mapping):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        mapped = model_dump(mode="json", exclude_none=True)
        if isinstance(mapped, dict):
            return mapped
    if value is None:
        return {}
    return {
        name: getattr(value, name)
        for name in ("model", "status", "usage", "output")
        if hasattr(value, name)
    }


def _input_type(item: object) -> str:
    payload = _object_mapping(item)
    value = payload.get("type") or payload.get("role")
    return value if isinstance(value, str) else "unknown"


def _to_messages(source: CodexProbeSource) -> tuple[LLMMessage, ...]:
    messages: list[LLMMessage] = []
    pending_calls: list[LLMToolCall] = []

    instructions = source.request.get("instructions")
    if isinstance(instructions, str) and instructions:
        messages.append(LLMSystemMessage(instructions))

    for raw_item in source.seed_input:
        item = _object_mapping(raw_item)
        item_type = item.get("type")
        if item_type == "function_call":
            pending_calls.append(_to_tool_call(item))
            continue

        if pending_calls:
            messages.append(LLMAssistantMessage(tool_calls=tuple(pending_calls)))
            pending_calls.clear()

        if item_type == "function_call_output":
            call_id = item.get("call_id")
            if isinstance(call_id, str):
                messages.append(
                    LLMToolMessage(
                        content=_text_value(item.get("output")),
                        tool_call_id=call_id,
                    )
                )
            continue
        if item_type in {"additional_tools", "reasoning"}:
            continue

        role = item.get("role")
        if role == "user":
            messages.append(LLMUserMessage(_message_text(item.get("content"))))
        elif role == "assistant":
            content = _message_text(item.get("content"))
            if content:
                messages.append(LLMAssistantMessage(content=content))
        elif role in {"system", "developer"}:
            content = _message_text(item.get("content"))
            if content:
                messages.append(LLMSystemMessage(content))

    if pending_calls:
        messages.append(LLMAssistantMessage(tool_calls=tuple(pending_calls)))
    if not messages or not isinstance(messages[-1], LLMUserMessage):
        raise ValueError("Replay seed must end with a user message")
    return tuple(messages)


def _to_tool_call(item: Mapping[str, object]) -> LLMToolCall:
    call_id = item.get("call_id")
    name = item.get("name")
    if not isinstance(call_id, str) or not isinstance(name, str):
        raise ValueError("Replay function_call is missing call_id or name")
    return LLMToolCall(
        id=call_id,
        function=LLMToolCallFunction(
            name=name,
            arguments_json=_text_value(item.get("arguments")),
        ),
    )


def _message_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, list):
        return _text_value(value)
    parts: list[str] = []
    for item in value:
        payload = _object_mapping(item)
        text = payload.get("text")
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts)


def _text_value(value: object) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _to_tools(source: CodexProbeSource) -> tuple[ToolDefinition[ToolRequest], ...]:
    raw_tools = source.request.get("tools")
    if not isinstance(raw_tools, list):
        raw_tools = _lite_tools_from_input(source.request.get("input"))
    if not raw_tools:
        raise ValueError("Replay source has no tools")
    tools: list[ToolDefinition[ToolRequest]] = []
    for raw_tool in raw_tools:
        tool = _object_mapping(raw_tool)
        name = tool.get("name")
        if not isinstance(name, str):
            raise ValueError("Replay tool is missing name")
        parameters = tool.get("parameters")
        if not isinstance(parameters, Mapping):
            raise ValueError(f"Replay tool '{name}' is missing parameters")
        description = tool.get("description")
        tools.append(
            _ReplayTool(
                name=name,
                description=description if isinstance(description, str) else "",
                schema=parameters,
            )
        )
    return tuple(tools)


def _lite_tools_from_input(value: object) -> list[object]:
    if not isinstance(value, list):
        return []
    for item in value:
        payload = _object_mapping(item)
        if payload.get("type") != "additional_tools":
            continue
        namespaces = payload.get("tools")
        if not isinstance(namespaces, list):
            return []
        for namespace in namespaces:
            namespace_payload = _object_mapping(namespace)
            tools = namespace_payload.get("tools")
            if isinstance(tools, list):
                return tools
    return []


def _build_port(
    *,
    credentials_file: str,
    timeout_seconds: float,
    trace_file: Path,
) -> ResponsesLLMPort:
    mapper = CodexMapper(
        capabilities_resolver=CodexModelCapabilitiesResolver(),
        responses_mapper=ResponsesGeneralMapper(),
        responses_lite_mapper=ResponsesLiteMapper(),
    )
    usage_mapper = DefaultLLMUsageMapper()
    return ResponsesLLMPort(
        credentials_file=credentials_file,
        timeout_seconds=timeout_seconds,
        credentials_datasource=CodexCredentialsDatasource(),
        request_logger=_TraceLogger(trace_file),
        request_mapper=mapper,
        response_mapper=ResponsesMapper(usage_mapper=usage_mapper),
        collector=CollectCodexResponse(),
        turn_session_manager=CodexTurnSessionManager(),
    )


def _build_request(
    *,
    source: CodexProbeSource,
    messages: tuple[LLMMessage, ...],
    model: LLMModelDefinition,
    tools: tuple[ToolDefinition[ToolRequest], ...],
    session_id: str,
    trace_file: Path,
) -> CodexLLMRequest:
    parallel_tool_calls = source.request.get("parallel_tool_calls")
    return CodexLLMRequest(
        messages=messages,
        model=model,
        tools=tools,
        parallel_tool_calls=(
            parallel_tool_calls if isinstance(parallel_tool_calls, bool) else False
        ),
        session_id=session_id,
        log_request_file=str(trace_file),
        log_override_file=True,
    )


def _continuation_messages(
    *,
    seed_messages: tuple[LLMMessage, ...],
    tool_calls: tuple[LLMToolCall, ...],
    source: CodexProbeSource,
) -> tuple[LLMMessage, ...]:
    recorded = list(source.recorded_tool_outputs)
    continuation: list[LLMMessage] = list(seed_messages)
    continuation.append(LLMAssistantMessage(tool_calls=tool_calls))
    for tool_call in tool_calls:
        matching_index = next(
            (
                index
                for index, output in enumerate(recorded)
                if output.name == tool_call.function.name
            ),
            None,
        )
        if matching_index is None:
            raise ValueError(f"No recorded output for tool '{tool_call.function.name}'")
        output = recorded.pop(matching_index)
        continuation.append(
            LLMToolMessage(content=output.output, tool_call_id=tool_call.id)
        )
    return tuple(continuation)


def _source_session_id(source: CodexProbeSource) -> str:
    value = source.request.get("prompt_cache_key")
    if isinstance(value, str) and value:
        return value
    headers = source.request.get("extra_headers")
    if isinstance(headers, Mapping):
        value = headers.get("session_id")
        if isinstance(value, str) and value:
            return value
    return str(uuid.uuid4())


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request_log", type=Path)
    parser.add_argument(
        "--credentials-file",
        type=Path,
        default=os.environ.get(
            "SKILLER_OPENAI_CODEX_CREDENTIALS_FILE",
            str(Path.home() / ".skiller/secrets/openai-codex.json"),
        ),
    )
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--trace-file", type=Path)
    parser.add_argument("--live", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        source = load_probe_source(args.request_log)
        messages = _to_messages(source)
        tools = _to_tools(source)
        model_name = source.request.get("model")
        if not isinstance(model_name, str) or not model_name:
            raise ValueError("Replay source has no model")
        model = LLMModelDefinition(model=model_name, context_window_tokens=1_050_000)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}))
        return 2

    summary = {
        "status": "DRY_RUN" if not args.live else "READY",
        "model": model.value,
        "seed_messages": len(messages),
        "tools": len(tools),
        "recorded_tool_outputs": len(source.recorded_tool_outputs),
        "repeat": args.repeat,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not args.live:
        print("DRY RUN: add --live to call Codex through ResponsesLLMPort.")
        return 0
    if args.repeat <= 0:
        print("ERROR: --repeat must be positive", file=sys.stderr)
        return 2
    if not args.credentials_file.is_file():
        print(
            json.dumps(
                {"status": "SKIPPED", "reason": "Codex credentials file is missing"},
                sort_keys=True,
            )
        )
        return 0

    trace_file = args.trace_file or Path(f"/tmp/skiller-codex-port-replay-{uuid.uuid4().hex}.jsonl")
    results: list[dict[str, object]] = []
    try:
        for attempt in range(1, args.repeat + 1):
            attempt_trace = trace_file.with_name(
                f"{trace_file.stem}-{attempt}{trace_file.suffix}"
            )
            session_id = _source_session_id(source)
            if args.repeat > 1:
                session_id = f"{session_id}-replay-{attempt}"
            port = _build_port(
                credentials_file=str(args.credentials_file),
                timeout_seconds=args.timeout_seconds,
                trace_file=attempt_trace,
            )
            seed_request = _build_request(
                source=source,
                messages=messages,
                model=model,
                tools=tools,
                session_id=session_id,
                trace_file=attempt_trace,
            )
            first = port.generate(seed_request)
            if not first.ok or not first.tool_calls:
                raise RuntimeError("seed did not return tool calls")
            if first.finish_type != LLMFinishType.TOOL_CALLS:
                raise RuntimeError(f"seed finish_type={first.finish_type!r}")
            continuation = _continuation_messages(
                seed_messages=messages,
                tool_calls=first.tool_calls,
                source=source,
            )
            second = port.generate(
                _build_request(
                    source=source,
                    messages=continuation,
                    model=model,
                    tools=tools,
                    session_id=session_id,
                    trace_file=attempt_trace,
                )
            )
            if not second.ok:
                raise RuntimeError(second.error or "continuation failed")
            if second.finish_type != LLMFinishType.STOP:
                raise RuntimeError(f"continuation finish_type={second.finish_type!r}")
            if second.usage is None or second.usage.total_tokens is None:
                raise RuntimeError("continuation did not include usage")
            results.append(
                {
                    "attempt": attempt,
                    "status": "SUCCEEDED",
                    "seed_tool_calls": len(first.tool_calls),
                    "continuation_finish_type": second.finish_type.value,
                    "continuation_total_tokens": second.usage.total_tokens,
                    "trace_file": str(attempt_trace),
                }
            )
    except Exception as exc:  # noqa: BLE001
        print(
            json.dumps(
                {"status": "FAILED", "error": f"{type(exc).__name__}: {exc}", "results": results},
                indent=2,
                sort_keys=True,
            )
        )
        return 1

    print(json.dumps({"status": "SUCCEEDED", "results": results}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
