# Architecture Rules

## Canonical Direction

`A -> B` means `A` depends on `B`.

The canonical dependency rule is:

```text
interfaces -> application -> domain <- infrastructure
```

1. `interfaces` calls application services/facades.
2. `application` orchestrates use cases and depends on `domain`.
3. `domain` contains models, rules, and ports.
4. `infrastructure` implements domain ports and depends on `domain`.
5. `di/container` composes concrete implementations.

## Layer Roles

- `domain`: pure models, business rules, and ports grouped by feature
- `application`: services and use cases
- `infrastructure`: DB, bus, MCP, config, skill loader
- `interfaces`: CLI / HTTP
- `di`: wiring
- `skills`: YAML/JSON outside `src`

## Allowed Dependencies

- `interfaces` may import application services/facades and `domain`
- `application` may import `domain`
- `infrastructure` may import `domain`
- `di` may import everything

`infrastructure -> domain` is intentionally narrow:

- infrastructure may implement one domain port
- infrastructure may use the models needed by that port
- infrastructure must not orchestrate other domain ports
- infrastructure must not coordinate cross-feature business flows

## Forbidden Dependencies

- `domain` must not import other layers
- `application` must not import `skiller.infrastructure.*`
- `application` must not define or import `skiller.application.ports.*`
- `infrastructure` must not import `skiller.application.*`
- `interfaces` must not call `application/use_cases` directly
- `application/services` must not import infrastructure concrete classes
- `use_cases` must not import `skiller.infrastructure.*`
- `infrastructure` must not import `interfaces`
- `infrastructure` must not consume or orchestrate unrelated domain ports
- `infrastructure` must not coordinate cross-domain behavior such as agent steering plus
  tool process execution
- `use_cases` must not depend on other `use_cases`
- `application/services` must not depend on other `application/services`

## Practical Rules

- The service orchestrates; it does not persist directly.
- Use cases own state transitions and emitted events.
- Ports must expose semantic contracts. If an operation represents a known domain fact,
  command, entry, payload, or request, pass a typed model instead of rebuilding the same
  concept from many scalar arguments.
- Do not use `dict[str, object]` in port signatures when the shape is stable and part of the
  domain. Reserve raw dict payloads for truly dynamic boundaries such as arbitrary external JSON
  or schemaless metadata that cannot be modeled yet.
- Infrastructure adapters should translate between storage and domain models, not reconstruct
  stable domain concepts from repeated primitive parameter lists.
- Ports live in the domain feature they belong to, for example:
  - `domain/agent/*_port.py`
  - `domain/run/*_port.py`
  - `domain/wait/*_port.py`
  - `domain/event/*_port.py`
  - `domain/step/*_port.py`
  - `domain/tool/*_port.py`
  - `domain/mcp/*_port.py`
  - `domain/shared/*_port.py`
- Do not create generic `domain/ports` or `application/ports` directories.
- Do not leave port wrappers, aliases, compatibility shims, or re-export modules.
- External SDKs, DB drivers, HTTP clients, and MCP adapters live in `infrastructure`.
- Environment reads belong in `infrastructure/config`.
- Infrastructure implements technical details only. It should not decide runtime behavior such as
  "ESC means interrupt this agent turn"; that belongs in `application`.
- Use cases must not depend on callbacks to continue runtime flow.
- Input normalization belongs in interfaces or adapters, not in use cases.
- A use case should be explainable in one short, concrete sentence.
