from pathlib import Path

from ollama import ChatResponse

from skiller.domain.agent.llm.finish_type import LLMFinishType
from skiller.domain.agent.llm.model import LLMResponse
from skiller.domain.agent.llm.port import LLMPort
from skiller.domain.agent.llm.provider_ollama import OllamaLLMRequest
from skiller.infrastructure.llm.logger.request_logger import LLMRequestLogger
from skiller.infrastructure.llm.mapper.llm_protocol_mapper import LLMProtocolMapper


def _load_ollama_client_class() -> type[object]:
    from ollama import Client

    return Client


class OllamaLLMPort(LLMPort[OllamaLLMRequest]):
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
        mapper: LLMProtocolMapper[OllamaLLMRequest, ChatResponse],
        request_logger: LLMRequestLogger,
    ) -> None:
        self.base_url = base_url.rstrip("/").removesuffix("/v1")
        self.timeout_seconds = timeout_seconds
        self.mapper = mapper
        self.request_logger = request_logger
        self.client = self._build_client()

    def generate(self, request: OllamaLLMRequest) -> LLMResponse:
        kwargs = self.mapper.to_kwargs(request)
        log_file = request.log_request_file
        if log_file is not None:
            self.request_logger.log_request(
                request=kwargs,
                file=Path(log_file).expanduser(),
                overwrite=request.log_override_file,
            )
        try:
            response = self.client.chat(**kwargs)
        except Exception as exc:  # noqa: BLE001
            error = f"Ollama request failed: {exc}"
            if log_file is not None:
                self.request_logger.log_error(error=error)
            return LLMResponse(
                generation_metrics=None,
                model=request.model,
                finish_type=LLMFinishType.ERROR_REQUEST_FAILED,
                error=error,
                error_code="request_failed",
            )
        if log_file is not None:
            self.request_logger.log_response(response=response)
        return self.mapper.to_response(response, request=request)

    def _build_client(self) -> object:
        client_class = _load_ollama_client_class()
        return client_class(host=self.base_url, timeout=self.timeout_seconds)
