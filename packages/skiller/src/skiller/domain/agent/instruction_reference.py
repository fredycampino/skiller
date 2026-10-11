import re

from skiller.domain.shared.file_reference import validate_file_reference

_PACKAGED_INSTRUCTION_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")


def is_packaged_instruction(reference: str) -> bool:
    return _PACKAGED_INSTRUCTION_PATTERN.fullmatch(reference) is not None


def parse_instruction_references(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError("Agent instructions must be a list")
    references: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("Agent instructions must contain non-empty strings")
        reference = item.strip()
        if not is_packaged_instruction(reference):
            validate_file_reference(reference)
        references.append(reference)
    return tuple(references)
