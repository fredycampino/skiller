# Architecture

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
- `infrastructure`: DB, bus, MCP, config, flow loader
- `interfaces`: CLI / HTTP
- `di`: wiring
- `flows`: YAML/JSON outside `src`

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
- Naming for ports, infrastructure port implementations, datasources, and mappers must follow
  [`naming-style.md`](naming-style.md).
- External SDKs, DB drivers, HTTP clients, and MCP adapters live in `infrastructure`.
- Environment reads belong in `infrastructure/config`.
- Infrastructure implements technical details only. It should not decide runtime behavior such as
  "ESC means interrupt this agent turn"; that belongs in `application`.
- Use cases must not depend on callbacks to continue runtime flow.
- Input normalization belongs in interfaces or adapters, not in use cases.
- A use case should be explainable in one short, concrete sentence.

## Service Boundary Pattern

New application services must use an explicit mapper boundary between interface adapters and
application services. Existing services should move to this pattern incrementally when touched.

The conceptual flow is:

```text
interface adapter scalar inputs
-> service mapper
-> application service receives typed input
-> use case receives typed input

use case returns typed result
-> application service returns typed result
-> service mapper
-> interface adapter returns public dict/list[dict]
```

Rules:

- interface adapters do not build domain or application input objects directly
- interface adapters do not serialize use case results directly
- application services receive typed inputs and return typed results
- application services orchestrate use cases but do not normalize scalar inputs
- use cases receive one typed input object when an operation has more than one input value
- use cases may receive a scalar only when the operation has one input value
- service mappers own scalar parsing, parameter sanitization, command/option normalization,
  option validation, and public output serialization
- service mappers return a typed input object from `to_*_input(...)` or raise `ValueError`
  with the public validation message
- interface adapters catch mapper `ValueError` and use the mapper to build the public error dict
- service mappers are dependencies created by `di/container`, not instantiated inside controllers
- stable public output shapes are produced by the mapper, not by the use case
- infrastructure adapters stay outside this flow and are injected through ports/use cases

Current reference implementation:

- `skiller.application.webhooks.mapper.WebhookServiceMapper`
- `skiller.application.webhooks.service.WebhookApplicationService`
- `skiller.interfaces.runtime_controller.RuntimeController` webhook methods

## Implementation Example

Generic shape:

```python
@dataclass(frozen=True)
class RegisterThingInput:
    name: str
    mode: ThingMode


@dataclass(frozen=True)
class RegisterThingResult:
    status: RegisterThingStatus
    name: str
    mode: ThingMode
    error: str | None = None


class ThingApplicationService:
    def __init__(self, register_thing_use_case: RegisterThingUseCase) -> None:
        self.register_thing_use_case = register_thing_use_case

    def register_thing(self, request: RegisterThingInput) -> RegisterThingResult:
        return self.register_thing_use_case.execute(request)


class ThingServiceMapper:
    def to_register_input(self, name: str, mode: str) -> RegisterThingInput:
        try:
            parsed_mode = ThingMode(mode.strip().lower())
        except ValueError as exc:
            raise ValueError("mode is invalid") from exc

        sanitized_name = name.strip()
        if not sanitized_name:
            raise ValueError("name is required")

        return RegisterThingInput(name=sanitized_name, mode=parsed_mode)

    def to_register_dict(self, result: RegisterThingResult) -> dict[str, object]:
        payload = {
            "status": result.status.value,
            "name": result.name,
            "mode": result.mode.value,
        }
        if result.error is not None:
            payload["error"] = result.error
        return payload

    def to_register_error_dict(self, name: str, error: str) -> dict[str, object]:
        return {
            "name": name,
            "status": "INVALID_INPUT",
            "error": error,
        }
```

The interface adapter uses the mapper on both sides of the application service call:

```python
try:
    request = self.thing_mapper.to_register_input(name, mode)
except ValueError as exc:
    return self.thing_mapper.to_register_error_dict(name, str(exc))

result = self.thing_service.register_thing(request)
return self.thing_mapper.to_register_dict(result)
```
