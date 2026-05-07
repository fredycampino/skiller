from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from skiller.application.agent.config.output_truncator import OutputTruncator
from skiller.application.agent.config.pii_sanitizer import PiiSanitizer
from skiller.application.agent.config.secret_sanitizer import SecretSanitizer


@dataclass(frozen=True)
class AgentEventOutputPolicy:
    truncate_enabled: bool = True
    pii_enabled: bool = True
    secrets_enabled: bool = True
    max_text_chars: int = 600
    max_json_chars: int = 4000
    max_array_items: int = 20


class AgentEventOutputSanitizer:
    def __init__(
        self,
        policy: AgentEventOutputPolicy | None = None,
        pii_sanitizer: PiiSanitizer | None = None,
        secret_sanitizer: SecretSanitizer | None = None,
        output_truncator: OutputTruncator | None = None,
    ) -> None:
        self.policy = policy or AgentEventOutputPolicy()
        self.pii_sanitizer = pii_sanitizer or PiiSanitizer()
        self.secret_sanitizer = secret_sanitizer or SecretSanitizer()
        self.output_truncator = output_truncator or OutputTruncator()

    def sanitize_args(self, args: dict[str, Any]) -> dict[str, Any]:
        sanitized = self._sanitize_value(args)
        if isinstance(sanitized, dict):
            return self._cap_json_payload(sanitized)
        return self._cap_json_payload({})

    def sanitize_output(self, output: dict[str, Any]) -> dict[str, Any]:
        text = self._sanitize_text(str(output.get("text", "")))
        value = self._sanitize_value(output.get("value"))
        if isinstance(value, (dict, list)):
            value = self._cap_json_payload(value)
        body_ref = output.get("body_ref")
        return {"text": text, "value": value, "body_ref": body_ref}

    def _sanitize_value(self, value: Any) -> Any:
        if isinstance(value, dict):
            sanitized: dict[str, Any] = {}
            for key, item in value.items():
                name = str(key)
                if self.policy.secrets_enabled and self.secret_sanitizer.is_sensitive_key(name):
                    sanitized[name] = self.secret_sanitizer.redacted_value
                    continue
                sanitized[name] = self._sanitize_value(item)
            return sanitized

        if isinstance(value, list):
            items = value
            if self.policy.truncate_enabled:
                items = self.output_truncator.truncate_list(
                    value,
                    max_items=self.policy.max_array_items,
                )
            return [self._sanitize_value(item) for item in items]

        if isinstance(value, str):
            return self._sanitize_text(value)

        return value

    def _sanitize_text(self, text: str) -> str:
        sanitized = text
        if self.policy.secrets_enabled:
            sanitized = self.secret_sanitizer.sanitize_text(sanitized)
        if self.policy.pii_enabled:
            sanitized = self.pii_sanitizer.sanitize_text(sanitized)
        if self.policy.truncate_enabled:
            return self.output_truncator.truncate_text(
                sanitized,
                max_chars=self.policy.max_text_chars,
            )
        return sanitized

    def _cap_json_payload(self, value: dict[str, Any] | list[Any]) -> Any:
        if not self.policy.truncate_enabled:
            return value
        return self.output_truncator.cap_json_payload(
            value,
            max_chars=self.policy.max_json_chars,
        )
