from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import cast

from openai.types.responses import Response, ResponsesServerEvent
from openai.types.responses.response import IncompleteDetails
from openai.types.responses.response_error import ResponseError
from openai.types.responses.response_output_item import ResponseOutputItem
from openai.types.responses.response_usage import InputTokensDetails, ResponseUsage
from pydantic import TypeAdapter, ValidationError

from skiller.infrastructure.llm.codex.codex_response_model import CodexResponseModel

_TERMINAL_STATUS_BY_EVENT = {
    "response.completed": "completed",
    "response.incomplete": "incomplete",
    "response.failed": "failed",
}
_MISSING = object()
_output_item_adapter = TypeAdapter(ResponseOutputItem)


class CollectCodexResponseError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        stream: tuple[ResponsesServerEvent, ...] = (),
    ) -> None:
        super().__init__(message)
        self.stream = stream


class CollectCodexResponse:
    def collect(self, stream: object, *, log_streaming: bool = False) -> CodexResponseModel:
        events: list[ResponsesServerEvent] = []
        try:
            return self._collect(
                stream=stream,
                events=events,
                log_streaming=log_streaming,
            )
        except CollectCodexResponseError as exc:
            raise CollectCodexResponseError(str(exc), stream=tuple(events)) from exc
        except Exception as exc:  # noqa: BLE001
            raise CollectCodexResponseError(
                f"Codex stream iteration failed: {exc}", stream=tuple(events)
            ) from exc

    def _collect(
        self,
        *,
        stream: object,
        events: list[ResponsesServerEvent],
        log_streaming: bool,
    ) -> CodexResponseModel:
        if not isinstance(stream, Iterable):
            raise CollectCodexResponseError("Codex stream must be iterable")

        output_items: list[ResponseOutputItem] = []
        for event in stream:
            if log_streaming:
                events.append(cast(ResponsesServerEvent, event))
            event_type = _field(event, "type")
            if not isinstance(event_type, str):
                raise CollectCodexResponseError("Codex stream event type must be a string")
            if event_type == "error":
                raise CollectCodexResponseError("Codex stream emitted an error event")
            if event_type == "response.output_item.done":
                output_item = _output_item(_field(event, "item"))
                if output_item is None:
                    raise CollectCodexResponseError(
                        "Codex stream output item done event must contain an output item"
                    )
                output_items.append(output_item)
                continue
            terminal_status = _TERMINAL_STATUS_BY_EVENT.get(event_type)
            if terminal_status is None:
                continue

            terminal_response = _response(_field(event, "response"))
            if terminal_response is None:
                raise CollectCodexResponseError(
                    f"Codex stream {event_type} event must contain a response object"
                )
            canonical_output = output_items
            if not canonical_output:
                canonical_output = _response_output(terminal_response)
            canonical_response = terminal_response.model_copy(
                update={
                    "status": terminal_status,
                    "output": canonical_output,
                }
            )
            return CodexResponseModel(
                response=canonical_response,
                stream=tuple(events),
            )

        raise CollectCodexResponseError("Codex stream ended without a terminal response")


def _field(value: object, name: str) -> object:
    if isinstance(value, Mapping):
        return value.get(name, _MISSING)
    return getattr(value, name, _MISSING)


def _response(value: object) -> Response | None:
    if isinstance(value, Response):
        return value
    if not isinstance(value, Mapping):
        return None

    response_fields = dict(value)
    raw_usage = response_fields.get("usage")
    if isinstance(raw_usage, Mapping):
        response_fields["usage"] = _response_usage(raw_usage)
    raw_error = response_fields.get("error")
    if isinstance(raw_error, Mapping):
        response_fields["error"] = ResponseError.model_construct(**dict(raw_error))
    raw_incomplete_details = response_fields.get("incomplete_details")
    if isinstance(raw_incomplete_details, Mapping):
        response_fields["incomplete_details"] = IncompleteDetails.model_construct(
            **dict(raw_incomplete_details)
        )
    return Response.model_construct(**response_fields)


def _response_usage(raw_usage: Mapping[object, object]) -> ResponseUsage:
    usage_fields = dict(raw_usage)
    raw_input_details = usage_fields.get("input_tokens_details")
    input_details = None
    if isinstance(raw_input_details, Mapping):
        input_details = InputTokensDetails.model_construct(**dict(raw_input_details))
    usage_fields["input_tokens_details"] = input_details
    return ResponseUsage.model_construct(**usage_fields)


def _response_output(response: Response) -> list[ResponseOutputItem]:
    raw_output = _field(response, "output")
    if raw_output is _MISSING or raw_output is None:
        return []
    if not isinstance(raw_output, list):
        raise CollectCodexResponseError("Codex terminal response output must be a list")

    output_items: list[ResponseOutputItem] = []
    for raw_item in raw_output:
        output_item = _output_item(raw_item)
        if output_item is None:
            raise CollectCodexResponseError(
                "Codex terminal response output must contain valid output items"
            )
        output_items.append(output_item)
    return output_items


def _output_item(value: object) -> ResponseOutputItem | None:
    if value is _MISSING or value is None:
        return None
    try:
        return _output_item_adapter.validate_python(value)
    except ValidationError:
        return None
