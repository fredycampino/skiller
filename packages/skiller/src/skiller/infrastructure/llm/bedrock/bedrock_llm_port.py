from __future__ import annotations

from skiller.domain.agent.llm.model import LLMResponse
from skiller.domain.agent.llm.port import LLMPort
from skiller.domain.agent.llm.provider_bedrock import BedrockLLMRequest
from skiller.infrastructure.llm.bedrock.bedrock_mapper import (
    to_bedrock_kwargs,
    to_port_llm_response,
)


def _load_boto3_session_class() -> type[object]:
    import boto3

    return boto3.Session


def _load_botocore_config_class() -> type[object]:
    from botocore.config import Config

    return Config


class BedrockLLMPort(LLMPort[BedrockLLMRequest]):
    def __init__(
        self,
        *,
        profile: str,
        timeout_seconds: float,
    ) -> None:
        self.profile = profile
        self.timeout_seconds = timeout_seconds
        self.client = self._build_client()

    def generate(self, request: BedrockLLMRequest) -> LLMResponse:
        try:
            kwargs = to_bedrock_kwargs(
                request,
                max_tokens=request.max_tokens,
            )
            response = self.client.converse(**kwargs)
        except Exception as exc:  # noqa: BLE001
            return LLMResponse(
                ok=False,
                model=request.model,
                error=f"Bedrock request failed: {exc}",
                error_code="request_failed",
            )
        return to_port_llm_response(response, fallback_model=request.model)

    def _build_client(self) -> object:
        session_class = _load_boto3_session_class()
        config_class = _load_botocore_config_class()
        session = session_class(profile_name=self.profile)
        return session.client(
            "bedrock-runtime",
            config=config_class(read_timeout=self.timeout_seconds),
        )
