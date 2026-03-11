from typing import Any


class NullLLM:
    def generate(self, messages: list[dict[str, str]], config: dict[str, Any] | None = None) -> dict[str, Any]:
        _ = messages
        _ = config
        return {"ok": False, "error": "LLM is not configured for llm_prompt steps"}
