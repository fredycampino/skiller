from skiller.infrastructure.llm.logger.request_logger import FileLLMRequestLogger


class BedrockFileLLMRequestLogger(FileLLMRequestLogger):
    def redact_request(
        self,
        *,
        request: object,
    ) -> object:
        # Redact here if the Bedrock request payload starts carrying sensitive data.
        return request

    def redact_response(
        self,
        *,
        response: object,
    ) -> object:
        # Redact here if the Bedrock response payload starts carrying sensitive data.
        return response
