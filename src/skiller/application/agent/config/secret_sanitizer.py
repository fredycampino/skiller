from __future__ import annotations

import re

_REDACTED = "***REDACTED***"
_TEXT_SECRET_PATTERN = re.compile(
    r"(?i)\b(token|password|secret|api[_-]?key|authorization)\b\s*[:=]\s*([^\s,;]+)"
)


class SecretSanitizer:
    def sanitize_text(self, text: str) -> str:
        return _TEXT_SECRET_PATTERN.sub(lambda match: f"{match.group(1)}={_REDACTED}", text)

    def is_sensitive_key(self, key: str) -> bool:
        normalized = key.strip().lower().replace("-", "").replace("_", "")
        markers = ("token", "password", "secret", "apikey", "authorization")
        return any(marker in normalized for marker in markers)

    @property
    def redacted_value(self) -> str:
        return _REDACTED
