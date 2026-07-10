import json
from collections.abc import Iterable
from dataclasses import asdict, is_dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Protocol

REDACTED_VALUE = "[redacted]"


class LLMRequestLogger(Protocol):
    def log_request(
        self,
        *,
        request: object,
        file: Path,
    ) -> None: ...

    def log_response(
        self,
        *,
        response: object,
    ) -> None: ...

    def log_error(
        self,
        *,
        error: str,
    ) -> None: ...


class FileLLMRequestLogger:
    def __init__(self, *, overwrite: bool = False) -> None:
        self.overwrite = overwrite
        self.current_path: Path | None = None
        self._sequence = 0

    def log_request(
        self,
        *,
        request: object,
        file: Path,
    ) -> None:
        file.parent.mkdir(parents=True, exist_ok=True)
        self._sequence += 1
        path = file if self.overwrite else _sequenced_path(file, self._sequence)
        safe_request = self.redact_request(request=request)
        payload = {
            "sequence": self._sequence,
            "request": to_log_value(safe_request),
            "response": None,
            "error": None,
        }
        _write_json(path, payload)
        self.current_path = path

    def log_response(
        self,
        *,
        response: object,
    ) -> None:
        path = self._current_path()
        payload = _read_json(path)
        safe_response = self.redact_response(response=response)
        payload["response"] = to_log_value(safe_response)
        payload["error"] = None
        _write_json(path, payload)

    def log_error(
        self,
        *,
        error: str,
    ) -> None:
        path = self._current_path()
        payload = _read_json(path)
        payload["response"] = None
        payload["error"] = error
        _write_json(path, payload)

    def redact_request(
        self,
        *,
        request: object,
    ) -> object:
        return request

    def redact_response(
        self,
        *,
        response: object,
    ) -> object:
        return response

    def _current_path(self) -> Path:
        if self.current_path is None:
            raise RuntimeError("LLM request log response requires a request log")
        return self.current_path


def redact_keys(
    value: object,
    *,
    keys: Iterable[str],
    replacement: str = REDACTED_VALUE,
) -> object:
    normalized_keys = {key.casefold() for key in keys}
    return _redact_keys(value, keys=normalized_keys, replacement=replacement)


def to_log_value(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, dict):
        return {str(key): to_log_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [to_log_value(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        return to_log_value(asdict(value))
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return to_log_value(model_dump(mode="json"))
    if isinstance(value, SimpleNamespace):
        return to_log_value(vars(value))
    return str(value)


def _redact_keys(
    value: object,
    *,
    keys: set[str],
    replacement: str,
) -> object:
    if isinstance(value, dict):
        redacted: dict[str, object] = {}
        for raw_key, item in value.items():
            key = str(raw_key)
            if key.casefold() in keys:
                redacted[key] = replacement
            else:
                redacted[key] = _redact_keys(
                    item,
                    keys=keys,
                    replacement=replacement,
                )
        return redacted
    if isinstance(value, list | tuple):
        return [
            _redact_keys(item, keys=keys, replacement=replacement)
            for item in value
        ]
    return value


def _sequenced_path(file: Path, sequence: int) -> Path:
    return file.with_name(f"{file.stem}-{sequence:04d}{file.suffix}")


def _read_json(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Invalid LLM request log file: {path}")
    return value


def _write_json(path: Path, payload: dict[str, object]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
