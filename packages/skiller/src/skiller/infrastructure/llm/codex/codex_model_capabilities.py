from dataclasses import dataclass
from enum import Enum
from typing import ClassVar


class CodexResponsesProtocol(str, Enum):
    GENERIC = "generic"
    LITE = "lite"


@dataclass(frozen=True)
class CodexModelCapabilities:
    protocol: CodexResponsesProtocol


class CodexModelCapabilitiesResolver:
    _GENERIC: ClassVar[CodexModelCapabilities] = CodexModelCapabilities(
        protocol=CodexResponsesProtocol.GENERIC,
    )
    _LITE: ClassVar[CodexModelCapabilities] = CodexModelCapabilities(
        protocol=CodexResponsesProtocol.LITE,
    )
    _MODEL_CAPABILITIES: ClassVar[dict[str, CodexModelCapabilities]] = {
        "gpt-5.4": _GENERIC,
        "gpt-5.5": _GENERIC,
        "gpt-5.6-sol": _LITE,
        "gpt-5.6-terra": _LITE,
        "gpt-5.6-luna": _LITE,
    }

    def resolve(self, model: str) -> CodexModelCapabilities:
        capabilities = self._MODEL_CAPABILITIES.get(model)
        if capabilities is not None:
            return capabilities
        if model.startswith("gpt-5.6-"):
            return self._LITE
        return self._GENERIC
