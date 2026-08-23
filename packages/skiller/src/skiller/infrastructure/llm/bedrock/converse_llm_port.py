from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from skiller.domain.agent.llm.finish_type import LLMFinishType
from skiller.domain.agent.llm.model import LLMResponse
from skiller.domain.agent.llm.port import LLMPort
from skiller.domain.agent.llm.provider_bedrock import BedrockLLMRequest
from skiller.infrastructure.llm.bedrock.collect_converse_response import (
    CollectConverseResponse,
    CollectConverseResponseError,
)
from skiller.infrastructure.llm.bedrock.converse_mapper import ConverseMapper
from skiller.infrastructure.llm.logger.request_logger import LLMRequestLogger
from skiller.infrastructure.llm.mapper.llm_protocol_mapper import LLMRequestMapper
from skiller.infrastructure.llm.mapper.request_error_mapper import request_error_code


def _load_boto3_session_class() -> type[object]:
    import boto3

    return boto3.Session


def _load_botocore_config_class() -> type[object]:
    from botocore.config import Config

    return Config


class ConverseLLMPort(LLMPort[BedrockLLMRequest]):
    def __init__(
        self,
        *,
        profile: str,
        timeout_seconds: float,
        request_logger: LLMRequestLogger,
        request_mapper: LLMRequestMapper[BedrockLLMRequest],
        response_mapper: ConverseMapper,
        collector: CollectConverseResponse,
    ) -> None:
        self.profile = profile
        self.timeout_seconds = timeout_seconds
        self.request_logger = request_logger
        self.request_mapper = request_mapper
        self.response_mapper = response_mapper
        self.collector = collector
        self.client = self._build_client()

    def generate(self, request: BedrockLLMRequest) -> LLMResponse:
        kwargs = self.request_mapper.to_kwargs(request)
        log_file = request.log_request_file
        capture_stream = request.log_streaming and log_file is not None
        if log_file is not None:
            self.request_logger.log_request(
                request=kwargs,
                file=Path(log_file).expanduser(),
                overwrite=request.log_override_file,
            )

        try:
            raw_response = self.client.converse_stream(**kwargs)
            stream = _stream(raw_response)
        except Exception as exc:  # noqa: BLE001
            error = f"Bedrock Converse request failed: {exc}"
            if log_file is not None:
                self.request_logger.log_error(error=error)
            return LLMResponse(
                model=request.model,
                finish_type=LLMFinishType.ERROR_REQUEST_FAILED,
                error=error,
                error_code=request_error_code(exc),
            )

        try:
            response = self.collector.collect(
                stream,
                log_streaming=capture_stream,
            )
        except CollectConverseResponseError as exc:
            error = f"Bedrock Converse stream failed: {exc}"
            if log_file is not None:
                self.request_logger.log_response(
                    response={"stream": exc.stream, "stream_error": error}
                )
            return LLMResponse(
                model=request.model,
                finish_type=LLMFinishType.ERROR_STREAM,
                error=error,
                error_code="stream_failed",
            )

        if log_file is not None:
            self.request_logger.log_response(response=response)
        return self.response_mapper.to_response(response, request=request)

    def _build_client(self) -> object:
        session_class = _load_boto3_session_class()
        config_class = _load_botocore_config_class()
        session = session_class(profile_name=self.profile)
        return session.client(
            "bedrock-runtime",
            config=config_class(read_timeout=self.timeout_seconds),
        )


def _stream(response: object) -> object:
    if not isinstance(response, Mapping) or "stream" not in response:
        raise ValueError("Bedrock Converse response missing stream")
    return response["stream"]
