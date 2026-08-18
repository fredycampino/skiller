"""Reproduce Codex tool-continuation streams without executing model tools.

The probe reads a Skiller Codex request log, reconstructs the request that
preceded its final tool batch, sends it, and then sends one tool continuation.
It records only protocol metadata. Prompt text, tool output, credentials,
reasoning content, and the opaque turn-state value are never written to disk.

Run without ``--live`` to validate the source and inspect the request shape
without contacting the provider.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import time
import uuid
import zlib
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Protocol

from skiller.infrastructure.llm.codex.codex_credentials_datasource import (
    CodexCredentialsDatasource,
    CodexCredentialsError,
)
from skiller.infrastructure.llm.codex.codex_llm_port import (
    CODEX_BASE_URL,
    _codex_headers,
)

TURN_STATE_HEADER = "x-codex-turn-state"
RESPONSES_LITE_HEADER = "x-openai-internal-codex-responses-lite"


class CodexProbeVariant(str, Enum):
    BASELINE = "baseline"
    TURN_STATE = "turn-state"
    REASONING = "reasoning"
    COMBINED = "combined"
    LITE = "lite"

    @property
    def replays_turn_state(self) -> bool:
        return self in {self.TURN_STATE, self.COMBINED, self.LITE}

    @property
    def preserves_reasoning(self) -> bool:
        return self in {self.REASONING, self.COMBINED, self.LITE}


@dataclass(frozen=True)
class RecordedToolOutput:
    name: str
    output: str


@dataclass(frozen=True)
class CodexProbeSource:
    request: dict[str, object]
    seed_input: tuple[dict[str, object], ...]
    recorded_tool_outputs: tuple[RecordedToolOutput, ...]
    sequence: int | None
    source_sha256: str


@dataclass(frozen=True)
class CodexProbeIdentity:
    session_id: str
    thread_id: str
    installation_id: str
    window_id: str
    turn_id: str
    turn_started_at_unix_ms: int

    @classmethod
    def from_source(cls, source: CodexProbeSource) -> CodexProbeIdentity:
        extra_headers = source.request.get("extra_headers")
        source_session_id = None
        if isinstance(extra_headers, Mapping):
            raw_session_id = extra_headers.get("session_id")
            if isinstance(raw_session_id, str) and raw_session_id:
                source_session_id = raw_session_id

        session_id = source_session_id or str(uuid.uuid4())
        return cls(
            session_id=session_id,
            thread_id=session_id,
            installation_id=str(uuid.uuid4()),
            window_id=str(uuid.uuid4()),
            turn_id=str(uuid.uuid4()),
            turn_started_at_unix_ms=int(time.time() * 1000),
        )


@dataclass(frozen=True)
class CodexProbeStreamResult:
    completed: bool
    terminal_event: str | None
    turn_state: str | None
    output_items: tuple[dict[str, object], ...]
    output_text: str
    event_count: int
    serialized_event_bytes: int
    error: str | None

    @property
    def function_calls(self) -> tuple[dict[str, object], ...]:
        calls: list[dict[str, object]] = []
        for item in self.output_items:
            if item.get("type") == "function_call":
                calls.append(item)
        return tuple(calls)


class CodexProbeStreamClient(Protocol):
    def stream(
        self,
        request: dict[str, object],
        *,
        phase: str,
    ) -> CodexProbeStreamResult: ...


class CodexProbeTraceWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("x", encoding="utf-8"):
            pass

    def write(self, event: str, **fields: object) -> None:
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": event,
            **fields,
        }
        line = json.dumps(record, ensure_ascii=False, sort_keys=True)
        with self.path.open("a", encoding="utf-8") as file:
            file.write(line)
            file.write("\n")
            file.flush()


class CodexOpenAIProbeClient:
    def __init__(
        self,
        *,
        access_token: str,
        account_id: str | None,
        timeout_seconds: float,
        trace_writer: CodexProbeTraceWriter,
    ) -> None:
        self.access_token = access_token
        self.account_id = account_id
        self.timeout_seconds = timeout_seconds
        self.trace_writer = trace_writer

    def stream(
        self,
        request: dict[str, object],
        *,
        phase: str,
    ) -> CodexProbeStreamResult:
        from openai import OpenAI  # type: ignore[import-not-found]

        started = time.monotonic()
        output_items: list[dict[str, object]] = []
        text_deltas: list[str] = []
        function_argument_deltas: list[str] = []
        completed = False
        terminal_event: str | None = None
        turn_state: str | None = None
        event_count = 0
        serialized_event_bytes = 0
        error: str | None = None

        client = OpenAI(
            api_key=self.access_token,
            base_url=CODEX_BASE_URL,
            timeout=self.timeout_seconds,
            default_headers=_codex_headers(self.account_id),
        )
        try:
            response_context = client.responses.with_streaming_response.create(**request)
            with response_context as raw_response:
                turn_state = raw_response.headers.get(TURN_STATE_HEADER)
                self.trace_writer.write(
                    "response_headers",
                    phase=phase,
                    elapsed_ms=_elapsed_ms(started),
                    status_code=raw_response.status_code,
                    http_version=raw_response.http_version,
                    headers=_safe_response_headers(raw_response.headers),
                )

                stream = raw_response.parse()
                for event in stream:
                    event_count += 1
                    event_payload = _external_object_to_dict(event)
                    event_bytes = len(
                        json.dumps(event_payload, ensure_ascii=False, separators=(",", ":")).encode(
                            "utf-8"
                        )
                    )
                    serialized_event_bytes += event_bytes
                    event_type = _external_field(event, "type")
                    event_type_text = event_type if isinstance(event_type, str) else "unknown"
                    self.trace_writer.write(
                        "stream_event",
                        phase=phase,
                        sequence=event_count,
                        elapsed_ms=_elapsed_ms(started),
                        serialized_bytes=event_bytes,
                        **_safe_event_metadata(event, event_type_text),
                    )

                    if event_type_text == "response.output_text.delta":
                        delta = _external_field(event, "delta")
                        if isinstance(delta, str):
                            text_deltas.append(delta)
                        continue

                    if event_type_text == "response.function_call_arguments.delta":
                        delta = _external_field(event, "delta")
                        if isinstance(delta, str):
                            function_argument_deltas.append(delta)
                        continue

                    if event_type_text == "response.output_item.done":
                        item = _external_field(event, "item")
                        item_payload = _external_object_to_dict(item)
                        if item_payload:
                            output_items.append(item_payload)
                        continue

                    if event_type_text == "response.completed":
                        completed = True
                        terminal_event = event_type_text
                        if not output_items:
                            response = _external_field(event, "response")
                            output_items.extend(_response_output_items(response))
                        continue

                    if event_type_text in {"response.failed", "response.incomplete", "error"}:
                        terminal_event = event_type_text
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
            self.trace_writer.write(
                "stream_exception",
                phase=phase,
                elapsed_ms=_elapsed_ms(started),
                exception_chain=_safe_exception_chain(exc),
                event_count=event_count,
                serialized_event_bytes=serialized_event_bytes,
            )
        finally:
            client.close()

        if error is None and not completed:
            error = "stream ended without response.completed"

        result = CodexProbeStreamResult(
            completed=completed,
            terminal_event=terminal_event,
            turn_state=turn_state,
            output_items=tuple(output_items),
            output_text="".join(text_deltas),
            event_count=event_count,
            serialized_event_bytes=serialized_event_bytes,
            error=error,
        )
        function_arguments = "".join(function_argument_deltas)
        self.trace_writer.write(
            "stream_result",
            phase=phase,
            elapsed_ms=_elapsed_ms(started),
            completed=result.completed,
            terminal_event=result.terminal_event,
            turn_state=_opaque_value_metadata(result.turn_state),
            output_item_types=dict(Counter(item.get("type", "unknown") for item in output_items)),
            output_text_chars=len(result.output_text),
            function_call_count=len(result.function_calls),
            event_count=result.event_count,
            serialized_event_bytes=result.serialized_event_bytes,
            function_arguments=_function_arguments_metadata(
                function_arguments,
                delta_events=len(function_argument_deltas),
            ),
            error=result.error,
        )
        return result


class CodexProbeRunner:
    def __init__(
        self,
        *,
        stream_client: CodexProbeStreamClient,
        trace_writer: CodexProbeTraceWriter,
    ) -> None:
        self.stream_client = stream_client
        self.trace_writer = trace_writer

    def run(
        self,
        source: CodexProbeSource,
        *,
        variant: CodexProbeVariant,
        identity: CodexProbeIdentity,
    ) -> tuple[CodexProbeStreamResult, CodexProbeStreamResult | None]:
        seed_request = build_seed_request(source, variant=variant, identity=identity)
        self.trace_writer.write(
            "request",
            phase="seed",
            summary=request_summary(seed_request),
        )
        seed_result = self.stream_client.stream(seed_request, phase="seed")

        continuation_request = build_continuation_request(
            source,
            seed_request=seed_request,
            seed_result=seed_result,
            variant=variant,
            identity=identity,
        )
        if continuation_request is None:
            self.trace_writer.write(
                "probe_stopped",
                reason="seed response contained no function calls",
            )
            return seed_result, None

        self.trace_writer.write(
            "request",
            phase="continuation",
            summary=request_summary(continuation_request),
        )
        continuation_result = self.stream_client.stream(
            continuation_request,
            phase="continuation",
        )
        return seed_result, continuation_result


def load_probe_source(path: Path) -> CodexProbeSource:
    source_bytes = path.read_bytes()
    payload = json.loads(source_bytes)
    if not isinstance(payload, dict):
        raise ValueError("Codex request log must contain a JSON object")

    raw_request = payload.get("request")
    if not isinstance(raw_request, dict):
        raise ValueError("Codex request log must contain a request object")

    raw_input = raw_request.get("input")
    if not isinstance(raw_input, list):
        raise ValueError("Codex request input must be a list")
    input_items = [_required_object(item, "Codex request input item") for item in raw_input]

    last_user_index = _last_user_message_index(input_items)
    if last_user_index is None:
        raise ValueError("Codex request input has no user message before the final tool batch")

    final_turn_items = input_items[last_user_index + 1 :]
    recorded_tool_outputs = _recorded_tool_outputs(final_turn_items)
    if not recorded_tool_outputs:
        raise ValueError("Codex request input has no final tool continuation to reconstruct")

    sequence = payload.get("sequence")
    parsed_sequence = (
        sequence if isinstance(sequence, int) and not isinstance(sequence, bool) else None
    )
    request = copy.deepcopy(raw_request)
    seed_input = tuple(copy.deepcopy(input_items[: last_user_index + 1]))
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    return CodexProbeSource(
        request=request,
        seed_input=seed_input,
        recorded_tool_outputs=recorded_tool_outputs,
        sequence=parsed_sequence,
        source_sha256=source_sha256,
    )


def build_seed_request(
    source: CodexProbeSource,
    *,
    variant: CodexProbeVariant,
    identity: CodexProbeIdentity,
) -> dict[str, object]:
    request = copy.deepcopy(source.request)
    request["input"] = [copy.deepcopy(item) for item in source.seed_input]
    return _apply_variant(request, variant=variant, identity=identity)


def build_continuation_request(
    source: CodexProbeSource,
    *,
    seed_request: dict[str, object],
    seed_result: CodexProbeStreamResult,
    variant: CodexProbeVariant,
    identity: CodexProbeIdentity,
) -> dict[str, object] | None:
    function_calls = seed_result.function_calls
    if not function_calls:
        return None

    request = copy.deepcopy(seed_request)
    raw_input = request.get("input")
    if not isinstance(raw_input, list):
        raise ValueError("Probe seed request input must be a list")
    continuation_input = [
        copy.deepcopy(_required_object(item, "Probe input item")) for item in raw_input
    ]

    if variant == CodexProbeVariant.LITE:
        continuation_input.extend(copy.deepcopy(item) for item in seed_result.output_items)
    else:
        if variant.preserves_reasoning:
            reasoning_items = [
                copy.deepcopy(item)
                for item in seed_result.output_items
                if item.get("type") == "reasoning"
            ]
            continuation_input.extend(reasoning_items)

        assistant_text = seed_result.output_text or _output_message_text(seed_result.output_items)
        if assistant_text:
            continuation_input.append({"role": "assistant", "content": assistant_text})
        continuation_input.extend(_generic_function_call(item) for item in function_calls)

    continuation_input.extend(
        _tool_result_items(function_calls, source.recorded_tool_outputs)
    )
    request["input"] = continuation_input

    extra_headers = request.get("extra_headers")
    headers = dict(extra_headers) if isinstance(extra_headers, Mapping) else {}
    headers.pop(TURN_STATE_HEADER, None)
    if variant.replays_turn_state and seed_result.turn_state is not None:
        headers[TURN_STATE_HEADER] = seed_result.turn_state
    request["extra_headers"] = headers

    if variant == CodexProbeVariant.LITE:
        request = _apply_lite_identity(request, identity=identity)
    return request


def request_summary(request: dict[str, object]) -> dict[str, object]:
    raw_input = request.get("input")
    input_items = raw_input if isinstance(raw_input, list) else []
    input_types = Counter(_input_item_type(item) for item in input_items)
    raw_tools = request.get("tools")
    tools = raw_tools if isinstance(raw_tools, list) else []
    raw_instructions = request.get("instructions")
    instructions = raw_instructions if isinstance(raw_instructions, str) else ""
    extra_headers = request.get("extra_headers")
    header_names = (
        sorted(str(name).lower() for name in extra_headers)
        if isinstance(extra_headers, Mapping)
        else []
    )
    wire_request = {key: value for key, value in request.items() if key != "extra_headers"}
    serialized_bytes = len(
        json.dumps(wire_request, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )
    return {
        "model": request.get("model"),
        "input_count": len(input_items),
        "input_types": dict(input_types),
        "instructions_chars": len(instructions),
        "top_level_tool_count": len(tools),
        "parallel_tool_calls": request.get("parallel_tool_calls"),
        "has_reasoning": "reasoning" in request,
        "include": request.get("include"),
        "responses_lite": RESPONSES_LITE_HEADER in header_names,
        "turn_state_sent": TURN_STATE_HEADER in header_names,
        "extra_header_names": header_names,
        "serialized_body_bytes": serialized_bytes,
    }


def _apply_variant(
    request: dict[str, object],
    *,
    variant: CodexProbeVariant,
    identity: CodexProbeIdentity,
) -> dict[str, object]:
    extra_headers = request.get("extra_headers")
    headers = dict(extra_headers) if isinstance(extra_headers, Mapping) else {}
    headers.pop(TURN_STATE_HEADER, None)
    headers.pop(RESPONSES_LITE_HEADER, None)
    request["extra_headers"] = headers

    if variant.preserves_reasoning:
        request["reasoning"] = {"effort": "medium"}
        request["include"] = ["reasoning.encrypted_content"]
    else:
        request.pop("reasoning", None)
        request.pop("include", None)

    if variant != CodexProbeVariant.LITE:
        return request

    instructions = request.pop("instructions", "")
    instruction_text = instructions if isinstance(instructions, str) else ""
    raw_tools = request.pop("tools", [])
    tools = raw_tools if isinstance(raw_tools, list) else []
    raw_input = request.get("input")
    input_items = raw_input if isinstance(raw_input, list) else []

    lite_prefix: list[dict[str, object]] = [
        {
            "type": "additional_tools",
            "role": "developer",
            "tools": _lite_tools(tools),
        }
    ]
    if instruction_text:
        lite_prefix.append(
            {
                "type": "message",
                "role": "developer",
                "content": [{"type": "input_text", "text": instruction_text}],
            }
        )
    lite_input = lite_prefix + [_lite_input_item(item) for item in input_items]
    request["input"] = lite_input
    request["parallel_tool_calls"] = False
    request["reasoning"] = {"effort": "medium", "context": "all_turns"}
    request["include"] = ["reasoning.encrypted_content"]
    return _apply_lite_identity(request, identity=identity)


def _apply_lite_identity(
    request: dict[str, object],
    *,
    identity: CodexProbeIdentity,
) -> dict[str, object]:
    model = request.get("model")
    model_text = model if isinstance(model, str) else ""
    turn_metadata = {
        "installation_id": identity.installation_id,
        "session_id": identity.session_id,
        "thread_id": identity.thread_id,
        "turn_id": identity.turn_id,
        "window_id": identity.window_id,
        "request_kind": "turn",
        "turn_started_at_unix_ms": identity.turn_started_at_unix_ms,
    }
    turn_metadata_json = json.dumps(turn_metadata, separators=(",", ":"), sort_keys=True)
    client_metadata = {
        "x-codex-installation-id": identity.installation_id,
        "session_id": identity.session_id,
        "thread_id": identity.thread_id,
        "x-codex-window-id": identity.window_id,
        "turn_id": identity.turn_id,
        "x-codex-turn-metadata": turn_metadata_json,
    }

    extra_headers = request.get("extra_headers")
    headers = dict(extra_headers) if isinstance(extra_headers, Mapping) else {}
    headers.update(
        {
            RESPONSES_LITE_HEADER: "true",
            "session_id": identity.session_id,
            "thread_id": identity.thread_id,
            "x-client-request-id": identity.thread_id,
            "x-codex-installation-id": identity.installation_id,
            "x-codex-window-id": identity.window_id,
            "x-codex-turn-metadata": turn_metadata_json,
            "x-codex-routing-hint": f"model={model_text}",
        }
    )
    request["extra_headers"] = headers

    extra_body = request.get("extra_body")
    body = dict(extra_body) if isinstance(extra_body, Mapping) else {}
    body["client_metadata"] = client_metadata
    request["extra_body"] = body
    return request


def _lite_tools(tools: list[object]) -> list[dict[str, object]]:
    namespace_tools: list[dict[str, object]] = []
    other_tools: list[dict[str, object]] = []
    for raw_tool in tools:
        tool = _required_object(raw_tool, "Codex tool")
        if tool.get("type") != "function":
            other_tools.append(copy.deepcopy(tool))
            continue
        namespace_tool = copy.deepcopy(tool)
        namespace_tool["strict"] = bool(namespace_tool.get("strict", False))
        namespace_tools.append(namespace_tool)

    if namespace_tools:
        other_tools.insert(
            0,
            {
                "type": "namespace",
                "name": "functions",
                "description": "",
                "tools": namespace_tools,
            },
        )
    return other_tools


def _lite_input_item(raw_item: object) -> dict[str, object]:
    item = copy.deepcopy(_required_object(raw_item, "Codex input item"))
    role = item.get("role")
    content = item.get("content")
    if role not in {"user", "assistant", "developer", "system"} or not isinstance(content, str):
        return item

    content_type = "output_text" if role == "assistant" else "input_text"
    mapped_role = "developer" if role == "system" else role
    return {
        "type": "message",
        "role": mapped_role,
        "content": [{"type": content_type, "text": content}],
    }


def _generic_function_call(item: dict[str, object]) -> dict[str, object]:
    return {
        "type": "function_call",
        "call_id": item.get("call_id"),
        "name": item.get("name"),
        "arguments": item.get("arguments", "{}"),
    }


def _tool_result_items(
    function_calls: tuple[dict[str, object], ...],
    recorded_outputs: tuple[RecordedToolOutput, ...],
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for index, function_call in enumerate(function_calls):
        call_id = function_call.get("call_id")
        name = function_call.get("name")
        if not isinstance(call_id, str) or not isinstance(name, str):
            continue

        output = json.dumps(
            {
                "ok": False,
                "diagnostic": "tool execution suppressed by codex_stream_probe",
            },
            separators=(",", ":"),
        )
        if index < len(recorded_outputs):
            recorded = recorded_outputs[index]
            if recorded.name == name:
                output = recorded.output
        results.append(
            {
                "type": "function_call_output",
                "call_id": call_id,
                "output": output,
            }
        )
    return results


def _recorded_tool_outputs(
    final_turn_items: list[dict[str, object]],
) -> tuple[RecordedToolOutput, ...]:
    call_names: dict[str, str] = {}
    call_order: list[str] = []
    output_by_call_id: dict[str, str] = {}
    for item in final_turn_items:
        item_type = item.get("type")
        call_id = item.get("call_id")
        if item_type == "function_call" and isinstance(call_id, str):
            name = item.get("name")
            if isinstance(name, str):
                call_names[call_id] = name
                call_order.append(call_id)
            continue
        if item_type != "function_call_output" or not isinstance(call_id, str):
            continue
        output = item.get("output")
        if isinstance(output, str):
            output_by_call_id[call_id] = output

    outputs: list[RecordedToolOutput] = []
    for call_id in call_order:
        name = call_names[call_id]
        output = output_by_call_id.get(call_id)
        if output is not None:
            outputs.append(RecordedToolOutput(name=name, output=output))
    return tuple(outputs)


def _last_user_message_index(input_items: list[dict[str, object]]) -> int | None:
    for index in range(len(input_items) - 1, -1, -1):
        if input_items[index].get("role") == "user":
            return index
    return None


def _input_item_type(item: object) -> str:
    if not isinstance(item, Mapping):
        return "invalid"
    item_type = item.get("type")
    if isinstance(item_type, str):
        return item_type
    role = item.get("role")
    return role if isinstance(role, str) else "unknown"


def _output_message_text(output_items: tuple[dict[str, object], ...]) -> str:
    parts: list[str] = []
    for item in output_items:
        if item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for raw_part in content:
            if not isinstance(raw_part, Mapping):
                continue
            text = raw_part.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)


def _response_output_items(response: object) -> list[dict[str, object]]:
    output = _external_field(response, "output")
    if not isinstance(output, list):
        return []
    items: list[dict[str, object]] = []
    for item in output:
        item_payload = _external_object_to_dict(item)
        if item_payload:
            items.append(item_payload)
    return items


def _external_object_to_dict(value: object) -> dict[str, object]:
    if isinstance(value, Mapping):
        return copy.deepcopy(dict(value))
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json", exclude_none=True)
        if isinstance(dumped, dict):
            return dumped
    return {}


def _external_field(source: object, name: str) -> object:
    if isinstance(source, Mapping):
        return source.get(name)
    return getattr(source, name, None)


def _safe_event_metadata(event: object, event_type: str) -> dict[str, object]:
    metadata: dict[str, object] = {"type": event_type}
    delta = _external_field(event, "delta")
    if isinstance(delta, str):
        metadata["delta_chars"] = len(delta)

    item = _external_field(event, "item")
    item_type = _external_field(item, "type")
    if isinstance(item_type, str):
        metadata["item_type"] = item_type
    item_id = _external_field(item, "id")
    if isinstance(item_id, str):
        metadata["item_id_prefix"] = item_id[:16]
    item_status = _external_field(item, "status")
    if isinstance(item_status, str):
        metadata["item_status"] = item_status
    item_name = _external_field(item, "name")
    if isinstance(item_name, str):
        metadata["item_name"] = item_name

    response = _external_field(event, "response")
    response_status = _external_field(response, "status")
    if isinstance(response_status, str):
        metadata["response_status"] = response_status
    response_output = _external_field(response, "output")
    if isinstance(response_output, list):
        metadata["response_output_count"] = len(response_output)
    return metadata


def _safe_response_headers(headers: Mapping[str, str]) -> dict[str, object]:
    safe_names = {
        "content-type",
        "content-encoding",
        "transfer-encoding",
        "server",
        "cf-ray",
        "x-request-id",
        "openai-request-id",
    }
    safe_headers: dict[str, object] = {}
    for name in safe_names:
        value = headers.get(name)
        if value is not None:
            safe_headers[name] = value
    safe_headers[TURN_STATE_HEADER] = _opaque_value_metadata(headers.get(TURN_STATE_HEADER))
    return safe_headers


def _opaque_value_metadata(value: str | None) -> dict[str, object]:
    if value is None:
        return {"present": False}
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return {
        "present": True,
        "length": len(value),
        "sha256_prefix": digest[:16],
    }


def _safe_exception_chain(exc: BaseException) -> list[dict[str, str]]:
    chain: list[dict[str, str]] = []
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append({"type": type(current).__name__, "message": str(current)})
        current = current.__cause__ or current.__context__
    return chain


def _function_arguments_metadata(
    arguments: str,
    *,
    delta_events: int,
) -> dict[str, object]:
    if not arguments:
        return {
            "chars": 0,
            "utf8_bytes": 0,
            "delta_events": delta_events,
            "json_complete": False,
        }

    argument_bytes = arguments.encode("utf-8")
    compressed_bytes = zlib.compress(argument_bytes)
    try:
        json.loads(arguments)
        json_complete = True
    except json.JSONDecodeError:
        json_complete = False

    character_classes = Counter(
        "whitespace"
        if character.isspace()
        else "alphanumeric"
        if character.isalnum()
        else "punctuation"
        for character in arguments
    )
    return {
        "chars": len(arguments),
        "utf8_bytes": len(argument_bytes),
        "delta_events": delta_events,
        "average_chars_per_delta": round(len(arguments) / delta_events, 3),
        "sha256_prefix": hashlib.sha256(argument_bytes).hexdigest()[:16],
        "zlib_bytes": len(compressed_bytes),
        "zlib_ratio": round(len(compressed_bytes) / len(argument_bytes), 4),
        "json_complete": json_complete,
        "character_classes": dict(character_classes),
    }


def _required_object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _elapsed_ms(started: float) -> int:
    return round((time.monotonic() - started) * 1000)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reproduce a two-request Codex tool continuation with sanitized tracing."
    )
    parser.add_argument(
        "--request-log",
        type=Path,
        default=Path("~/.skiller/logs/request/codex/request.json").expanduser(),
        help="Skiller Codex request log containing the failed continuation.",
    )
    parser.add_argument(
        "--credentials-file",
        type=Path,
        default=Path("~/.skiller/secrets/openai-codex.json").expanduser(),
        help="Codex OAuth credential file. It is read only when --live is set.",
    )
    parser.add_argument(
        "--variant",
        type=CodexProbeVariant,
        choices=list(CodexProbeVariant),
        default=CodexProbeVariant.BASELINE,
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=120,
        help="Per-read timeout used by the same OpenAI client as CodexLLMPort.",
    )
    parser.add_argument(
        "--trace-file",
        type=Path,
        help="JSONL trace path. Default: a unique file below /tmp.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Actually call the private Codex endpoint and consume account quota.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        source = load_probe_source(args.request_log)
        identity = CodexProbeIdentity.from_source(source)
        seed_request = build_seed_request(source, variant=args.variant, identity=identity)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "variant": args.variant.value,
                "source_sequence": source.sequence,
                "source_sha256": source.source_sha256,
                "recorded_tool_outputs": len(source.recorded_tool_outputs),
                "seed_request": request_summary(seed_request),
                "live": args.live,
            },
            indent=2,
            sort_keys=True,
        )
    )
    if not args.live:
        print("DRY RUN: add --live to contact the Codex endpoint.")
        return 0

    trace_file = args.trace_file
    if trace_file is None:
        trace_id = uuid.uuid4().hex
        trace_file = Path(f"/tmp/skiller-codex-probe-{trace_id}.jsonl")

    try:
        trace_writer = CodexProbeTraceWriter(trace_file)
        credentials = CodexCredentialsDatasource().load(str(args.credentials_file))
    except (CodexCredentialsError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    trace_writer.write(
        "probe_started",
        variant=args.variant.value,
        source_sequence=source.sequence,
        source_sha256=source.source_sha256,
        source_request_summary=request_summary(source.request),
        seed_request_summary=request_summary(seed_request),
        recorded_tool_output_count=len(source.recorded_tool_outputs),
    )
    client = CodexOpenAIProbeClient(
        access_token=credentials.access_token,
        account_id=credentials.account_id,
        timeout_seconds=args.timeout_seconds,
        trace_writer=trace_writer,
    )
    runner = CodexProbeRunner(stream_client=client, trace_writer=trace_writer)
    seed_result, continuation_result = runner.run(
        source,
        variant=args.variant,
        identity=identity,
    )

    success = continuation_result is not None and continuation_result.completed
    trace_writer.write(
        "probe_finished",
        success=success,
        seed_completed=seed_result.completed,
        continuation_completed=(
            continuation_result.completed if continuation_result is not None else None
        ),
    )
    print(f"trace_file={trace_file}")
    print(f"seed_completed={seed_result.completed}")
    if continuation_result is None:
        print("continuation=not_sent (seed produced no function calls)")
        return 1
    print(f"continuation_completed={continuation_result.completed}")
    print(f"continuation_error={continuation_result.error}")
    return 0 if success else 1

