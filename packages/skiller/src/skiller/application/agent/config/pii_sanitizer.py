from __future__ import annotations

import re

_REDACTED_EMAIL = "***REDACTED_EMAIL***"
_REDACTED_PHONE = "***REDACTED_PHONE***"

_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")


class PiiSanitizer:
    def sanitize_text(self, text: str) -> str:
        redacted = _EMAIL_PATTERN.sub(_REDACTED_EMAIL, text)
        redacted = _PHONE_PATTERN.sub(_REDACTED_PHONE, redacted)
        return redacted
