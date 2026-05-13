# TUI Code Style Rules

## Checklist

- Do not use `dict` when an explicit `dataclass` fits the contract.
- Do not use plain `str` when the domain is closed. Use `Enum`, `StrEnum`, `Kind`, or an equivalent model.
- Do not add fallbacks in functions or constructors. Validate early.
- Do not postpone validation with permissive defaults.
- Return explicit result models when failure is part of the normal flow.
- Put error data in the result model when possible.
- Do not use exceptions as normal control flow between layers.
- Raise exceptions only for truly exceptional situations.
- Keep code flat.
- Avoid nested `if` chains.
- Prefer direct rules over branching pyramids.
- A function should read like a small rule table.
- Split logic early when branching starts to grow.
- Treat a file near `500` lines as a warning sign.
- If a file approaches `500` lines, split it by responsibility.
