from enum import Enum


class AgentLLMModelEnum(str, Enum):
    model_context_window_tokens: int

    def __new__(
        cls,
        value: str,
        model_context_window_tokens: int,
    ) -> "AgentLLMModelEnum":
        item = str.__new__(cls, value)
        item._value_ = value
        item.model_context_window_tokens = model_context_window_tokens
        return item
