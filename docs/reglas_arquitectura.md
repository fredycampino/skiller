# Reglas de Arquitectura

## Objetivo
Mantener una arquitectura por capas consistente y evitar acoplamientos accidentales.

## Fuente mantenida
Las reglas operativas y de mantenimiento diario viven en:

- `.codex/skills/skiller-dev/references/architecture-rules.md`
- `.codex/skills/skiller-dev/references/runtime-patterns.md`
- `.codex/skills/skiller-dev/references/code-style.md`

Este documento queda como resumen corto del marco arquitectónico del proyecto.

## Regla canónica
1. `interfaces/controllers` -> `application/services`
2. `application/services` -> `application/use_cases`
3. `application/use_cases` -> `application/ports`
4. `infrastructure` implementa esos `ports`
5. `di/container` compone todo

## Capas
- `domain`: modelos y reglas puras
- `application`: services, use cases y ports
- `infrastructure`: adaptadores concretos
- `interfaces`: CLI / HTTP
- `di`: wiring
- `skills`: YAML/JSON declarativo fuera de `src`

## Reglas mínimas
- `domain` no importa otras capas
- `interfaces` entra por `application/services`
- `application/services` no importa infraestructura concreta
- `use_cases` no importan `skiller.infrastructure.*`
- `infrastructure` no importa `interfaces`

## Nota
Si hay conflicto entre este resumen y las referencias de `.codex/skills/skiller-dev`, mantener las referencias de la skill y luego actualizar este resumen.
