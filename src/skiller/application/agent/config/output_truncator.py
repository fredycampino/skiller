from __future__ import annotations

import json
from typing import Any


class OutputTruncator:
    def truncate_text(self, text: str, *, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        return f"{text[:max_chars].rstrip()}..."

    def truncate_list(self, items: list[Any], *, max_items: int) -> list[Any]:
        return items[:max_items]

    def cap_json_payload(self, value: dict[str, Any] | list[Any], *, max_chars: int) -> Any:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True)
        if len(raw) <= max_chars:
            return value

        preview = raw[:max_chars].rstrip()
        return {
            "truncated": True,
            "preview": f"{preview}...",
        }
