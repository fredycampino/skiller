from enum import Enum


class LLMFinishType(str, Enum):
    STOP = "stop"
    TOOL_CALLS = "tool_calls"
    INVALID_RESPONSE_LENGTH = "invalid_response_length"
    INVALID_RESPONSE_CONTENT_FILTER = "invalid_response_content_filter"
    ERROR_API_KEY_MISSING = "error_api_key_missing"
    ERROR_REQUEST_FAILED = "error_request_failed"
    ERROR_STREAM = "error_stream"
    ERROR_MISSING_CHOICES = "error_missing_choices"
    ERROR_MISSING_MESSAGE = "error_missing_message"
    ERROR_MISSING_FINISH_REASON = "error_missing_finish_reason"
    ERROR_MISSING_CONTENT = "error_missing_content"
    ERROR_MISSING_TOOL_CALLS = "error_missing_tool_calls"
    ERROR_MALFORMED_RESPONSE = "error_malformed_response"
    UNKNOWN = "unknown"
