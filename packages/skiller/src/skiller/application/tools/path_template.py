import re
from collections.abc import Mapping


def resolve_tool_path_template(
    raw: str,
    *,
    tool_name: str,
    values: Mapping[str, str],
) -> str:
    value = raw.strip()
    for name, resolved in values.items():
        value = value.replace("{{" + name + "}}", resolved)

    if re.search(r"{{|}}", value):
        raise ValueError(f"Tool '{tool_name}' has unsupported path template: {raw}")
    return value
