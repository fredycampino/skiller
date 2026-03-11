# Architecture Rules

## Canonical Direction

1. `interfaces/controllers` -> `application/services`
2. `application/services` -> `application/use_cases`
3. `application/use_cases` -> `application/ports`
4. `infrastructure` implements those `ports`
5. `di/container` composes everything

## Layer Roles

- `domain`: pure models and business rules
- `application`: services, use cases, ports
- `infrastructure`: DB, bus, MCP, config, skill loader
- `interfaces`: CLI / HTTP
- `di`: wiring
- `skills`: YAML/JSON outside `src`

## Allowed Dependencies

- `interfaces` may import `application/services`
- `application/services` may import `use_cases`
- `use_cases` may import `ports` and `domain`
- `infrastructure` may import `ports` and `domain`
- `di` may import everything

## Forbidden Dependencies

- `domain` must not import other layers
- `interfaces` must not call `use_cases` directly
- `application/services` must not import infrastructure concrete classes
- `use_cases` must not import `skiller.infrastructure.*`
- `infrastructure` must not import `interfaces`
- `use_cases` must not depend on other `use_cases`
- `application/services` must not depend on other `application/services`

## Practical Rules

- The service orchestrates; it does not persist directly.
- Use cases own state transitions and emitted events.
- External SDKs, DB drivers, HTTP clients, and MCP adapters live in `infrastructure`.
- Environment reads belong in `infrastructure/config`.
- Use cases must not depend on callbacks to continue runtime flow.
- Input normalization belongs in interfaces or adapters, not in use cases.
- A use case should be explainable in one short, concrete sentence.
