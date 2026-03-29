from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LargeResultTruncator:
    max_string_chars: int = 200

    def truncate(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return self._truncate_object(value)
        if isinstance(value, list):
            return {
                "truncated": True,
                "type": "array",
                "items_count": len(value),
            }
        if isinstance(value, str):
            summary: dict[str, Any] = {
                "truncated": True,
                "type": "string",
                "text": self._truncate_string(value),
            }
            if len(value) > self.max_string_chars:
                summary["text_length"] = len(value)
            return summary
        if isinstance(value, bool):
            return {
                "truncated": True,
                "type": "boolean",
                "value": value,
            }
        if isinstance(value, int):
            return {
                "truncated": True,
                "type": "integer",
                "value": value,
            }
        if isinstance(value, float):
            return {
                "truncated": True,
                "type": "number",
                "value": value,
            }
        if value is None:
            return {
                "truncated": True,
                "type": "null",
                "value": None,
            }
        return {
            "truncated": True,
            "type": "unknown",
        }

    def _truncate_object(self, value: dict[str, Any]) -> dict[str, Any]:
        summary: dict[str, Any] = {"truncated": True}
        for key, item in value.items():
            if isinstance(item, str):
                summary[key] = self._truncate_string(item)
                if len(item) > self.max_string_chars:
                    summary[f"{key}_length"] = len(item)
                continue

            if isinstance(item, (int, float, bool)) or item is None:
                summary[key] = item
                continue

            if isinstance(item, list):
                summary[f"{key}_count"] = len(item)
                continue

            if isinstance(item, dict):
                summary[f"{key}_keys"] = sorted(str(entry_key) for entry_key in item.keys())

        return summary

    def _truncate_string(self, value: str) -> str:
        if len(value) <= self.max_string_chars:
            return value
        if self.max_string_chars <= 3:
            return value[: self.max_string_chars]
        return value[: self.max_string_chars - 3] + "..."
