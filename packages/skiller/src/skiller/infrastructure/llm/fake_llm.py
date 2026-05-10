from typing import Any


class FakeLLM:
    def __init__(self, *, response_json: str, model: str = "fake-llm") -> None:
        self.response_json = response_json
        self.model = model

    def generate(
        self,
        messages: list[dict[str, str]],
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        _ = messages
        _ = config
        return {
            "ok": True,
            "content": self.response_json,
            "model": self.model,
        }
