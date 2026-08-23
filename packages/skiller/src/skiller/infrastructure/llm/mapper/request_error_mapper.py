from collections.abc import Mapping


def request_error_code(error: Exception) -> str:
    response = getattr(error, "response", None)
    if not isinstance(response, Mapping):
        return "request_failed"
    provider_error = response.get("Error")
    if isinstance(provider_error, Mapping):
        provider_code = provider_error.get("Code")
        provider_message = provider_error.get("Message")
        if (
            provider_code == "AccessDeniedException"
            and isinstance(provider_message, str)
            and "not available for this account" in provider_message.casefold()
        ):
            return "model_not_available"
        if (
            provider_code == "ValidationException"
            and isinstance(provider_message, str)
            and "model identifier is invalid" in provider_message.casefold()
        ):
            return "invalid_model"
    metadata = response.get("ResponseMetadata")
    if not isinstance(metadata, Mapping):
        return "request_failed"
    status_code = metadata.get("HTTPStatusCode")
    if not isinstance(status_code, int):
        return "request_failed"
    if status_code == 401:
        return "unauthorized"
    if status_code == 403:
        return "forbidden"
    if status_code == 400:
        return "bad_request"
    if status_code == 429:
        return "rate_limit"
    if status_code >= 500:
        return "server_error"
    return "request_failed"
