from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from skiller.domain.agent.llm.model import LLMResponse
from skiller.domain.agent.llm.port import LLMPort
from skiller.domain.agent.llm.provider_bedrock import BedrockLLMRequest
from skiller.infrastructure.llm.bedrock.bedrock_llm_port import (
    _load_boto3_session_class,
    _load_botocore_config_class,
)
from skiller.infrastructure.llm.logger.request_logger import LLMRequestLogger
from skiller.infrastructure.llm.mapper.llm_protocol_mapper import LLMProtocolMapper


class BedrockStreamingLLMPort(LLMPort[BedrockLLMRequest]):
    """Bedrock client that uses the streaming Converse API.

    Functionally equivalent to :class:`BedrockLLMPort` but calls
    ``converse_stream`` (which requires the ``bedrock:InvokeModelWithResponseStream``
    IAM action) instead of ``converse`` (``bedrock:InvokeModel``).

    Streaming and mapping are kept as separate concerns: this port drains the
    event stream and reassembles the *complete* response using the same shape the
    non-streaming ``converse`` API returns, then delegates to the shared
    :class:`BedrockMapper`.
    """

    def __init__(
        self,
        *,
        profile: str,
        timeout_seconds: float,
        request_logger: LLMRequestLogger,
        mapper: LLMProtocolMapper[BedrockLLMRequest, object],
    ) -> None:
        self.profile = profile
        self.timeout_seconds = timeout_seconds
        self.request_logger = request_logger
        self.mapper = mapper
        self.client = self._build_client()

    def generate(self, request: BedrockLLMRequest) -> LLMResponse:
        kwargs = self.mapper.to_kwargs(request)
        log_file = request.log_request_file
        if log_file is not None:
            self.request_logger.log_request(
                request=kwargs,
                file=Path(log_file).expanduser(),
                overwrite=request.log_override_file,
            )

        try:
            stream = self.client.converse_stream(**kwargs)["stream"]
            response = _collect_converse_response(stream)
        except Exception as exc:  # noqa: BLE001
            error = f"Bedrock streaming request failed: {exc}"
            if log_file is not None:
                self.request_logger.log_error(error=error)
            return LLMResponse(
                ok=False,
                model=request.model,
                error=error,
                error_code="request_failed",
            )

        if log_file is not None:
            self.request_logger.log_response(response=response)

        return self.mapper.to_response(response, request=request)

    def _build_client(self) -> object:
        session_class = _load_boto3_session_class()
        config_class = _load_botocore_config_class()
        session = session_class(profile_name=self.profile)
        return session.client(
            "bedrock-runtime",
            config=config_class(read_timeout=self.timeout_seconds),
        )


def _collect_converse_response(stream: object) -> dict[str, object]:
    """Drain a ``converse_stream`` event stream into a ``converse``-shaped dict.

    The streaming API emits incremental events (``contentBlockStart``,
    ``contentBlockDelta``, ``messageStop``, ``metadata``). We accumulate them per
    content-block index and rebuild the same structure the non-streaming
    ``converse`` call returns, so a single mapper can handle both clients.
    """
    text_parts: dict[int, list[str]] = {}
    tool_parts: dict[int, dict[str, object]] = {}
    stop_reason: str | None = None
    usage: object | None = None

    for event in stream:
        if not isinstance(event, Mapping):
            continue
        if "contentBlockStart" in event:
            start = event["contentBlockStart"]
            if not isinstance(start, Mapping):
                continue
            index = start.get("contentBlockIndex")
            tool_use = start.get("start")
            tool_use = tool_use.get("toolUse") if isinstance(tool_use, Mapping) else None
            if isinstance(index, int) and isinstance(tool_use, Mapping):
                tool_parts[index] = {
                    "toolUseId": tool_use.get("toolUseId"),
                    "name": tool_use.get("name"),
                    "input_chunks": [],
                }
        elif "contentBlockDelta" in event:
            block = event["contentBlockDelta"]
            if not isinstance(block, Mapping):
                continue
            index = block.get("contentBlockIndex")
            delta = block.get("delta")
            if not isinstance(index, int) or not isinstance(delta, Mapping):
                continue
            text = delta.get("text")
            if isinstance(text, str):
                text_parts.setdefault(index, []).append(text)
            tool_delta = delta.get("toolUse")
            if isinstance(tool_delta, Mapping) and index in tool_parts:
                partial = tool_delta.get("input")
                if isinstance(partial, str):
                    chunks = tool_parts[index]["input_chunks"]
                    if isinstance(chunks, list):
                        chunks.append(partial)
        elif "messageStop" in event:
            message_stop = event["messageStop"]
            if isinstance(message_stop, Mapping):
                reason = message_stop.get("stopReason")
                if isinstance(reason, str):
                    stop_reason = reason
        elif "metadata" in event:
            metadata = event["metadata"]
            if isinstance(metadata, Mapping):
                usage = metadata.get("usage")

    content: list[dict[str, object]] = []
    for index in sorted(text_parts.keys() | tool_parts.keys()):
        if index in tool_parts:
            block = tool_parts[index]
            chunks = block.get("input_chunks")
            raw_input = "".join(chunks) if isinstance(chunks, list) else ""
            content.append(
                {
                    "toolUse": {
                        "toolUseId": block.get("toolUseId"),
                        "name": block.get("name"),
                        "input": _parse_tool_input(raw_input),
                    }
                }
            )
        else:
            content.append({"text": "".join(text_parts[index])})

    response: dict[str, object] = {
        "output": {"message": {"role": "assistant", "content": content}},
    }
    if stop_reason is not None:
        response["stopReason"] = stop_reason
    if usage is not None:
        response["usage"] = usage
    return response


def _parse_tool_input(raw_input: str) -> dict[str, object]:
    if not raw_input.strip():
        return {}
    try:
        parsed = json.loads(raw_input)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {"value": parsed}
