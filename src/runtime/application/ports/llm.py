from typing import Any, Protocol


class LLMAdapter(Protocol):
    def generate(self, messages: list[dict[str, str]], config: dict[str, Any] | None = None) -> dict[str, Any]:
        ...
