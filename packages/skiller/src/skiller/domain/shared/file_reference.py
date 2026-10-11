import os.path
import re
from collections.abc import Mapping
from pathlib import Path

_VARIABLE = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))")


def validate_file_reference(reference: str) -> None:
    reference = reference.strip()
    if "\x00" in reference:
        raise ValueError("File reference must not contain null bytes")
    if not reference:
        raise ValueError("File reference must not be empty")
    if "{{" in reference or "}}" in reference:
        raise ValueError("File references do not support templates")
    if "$" in _VARIABLE.sub("", reference):
        raise ValueError("Invalid environment variable syntax in file reference")
    if reference.startswith("~") and reference != "~" and not reference.startswith("~/"):
        raise ValueError("File references only support ~ or ~/ home expansion")


def resolve_file_reference(
    reference: str, *, environment: Mapping[str, str], base_dir: Path, home_dir: Path
) -> Path:
    """Expand a file reference without reading environment or filesystem state."""
    validate_file_reference(reference)
    if not base_dir.is_absolute() or not home_dir.is_absolute():
        raise ValueError("File reference base and home directories must be absolute")

    def expand(match: re.Match[str]) -> str:
        name = match.group(1) or match.group(2)
        value = environment.get(name)
        if value is None or not value.strip():
            raise ValueError(f"Missing or empty environment variable: {name}")
        return value

    expanded = _VARIABLE.sub(expand, reference.strip())
    if "\x00" in expanded:
        raise ValueError("File reference must not contain null bytes")
    if expanded == "~":
        expanded = str(home_dir)
    elif expanded.startswith("~/"):
        expanded = str(home_dir / expanded[2:])
    path = Path(expanded)
    if not path.is_absolute():
        path = base_dir / path
    return Path(os.path.normpath(str(path)))
