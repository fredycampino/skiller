# Naming Style

These rules define names that can be checked mechanically. New files and touched files must follow
them. Existing names that do not match this document are not precedent.

## Domain Ports

Domain ports live under the domain feature that owns the contract.

```text
packages/skiller/src/skiller/domain/<feature>/<concept>_port.py
```

The class name must be the PascalCase concept plus `Port`.

```python
class RunStorePort(Protocol):
    ...
```

Rules:

- domain port files end in `_port.py`
- domain port classes end in `Port`
- domain port classes are `Protocol`
- domain port names describe the semantic capability, not the concrete technology
- do not create generic `domain/ports` or `application/ports` directories

Examples:

```text
domain/run/run_store_port.py              -> RunStorePort
domain/run/run_agent_store_port.py        -> RunAgentStorePort
domain/event/runtime_event_store_port.py  -> RuntimeEventStorePort
domain/agent/llm_port.py                  -> LLMPort
```

## Infrastructure Port Implementations

Infrastructure classes that implement a domain port must make that explicit in their filename and
class name.

```text
packages/skiller/src/skiller/infrastructure/<area>/<tech>_<concept>_port.py
```

The class name must be the PascalCase technology plus the PascalCase concept plus `Port`.

```python
class SqliteRunStorePort(RunStorePort):
    ...
```

Rules:

- implementation files for domain ports end in `_port.py`
- implementation classes for domain ports end in `Port`
- the prefix names the concrete technology, provider, or adapter family
- the concept part matches the domain port concept
- one infrastructure port implementation should implement one domain port
- infrastructure port implementations are wired in `di/container`, not imported by application code

Examples:

```text
infrastructure/db/sqlite_run_store_port.py
  -> SqliteRunStorePort implements RunStorePort

infrastructure/db/sqlite_run_agent_store_port.py
  -> SqliteRunAgentStorePort implements RunAgentStorePort

infrastructure/db/sqlite_runtime_event_store_port.py
  -> SqliteRuntimeEventStorePort implements RuntimeEventStorePort

infrastructure/llm/codex/codex_llm_port.py
  -> CodexLLMPort implements LLMPort[CodexLLMRequest]
```

## Infrastructure Datasources

Datasources are infrastructure-only helpers for technical storage or external payload access. A
datasource is not a domain port and must not be injected into application code.

```text
packages/skiller/src/skiller/infrastructure/<area>/<tech>_<concept>_datasource.py
```

The class name must be the PascalCase technology plus the PascalCase concept plus `Datasource`.

```python
class SqliteAgentContextDatasource:
    ...
```

Rules:

- datasource files end in `_datasource.py`
- datasource classes end in `Datasource`
- datasources do not implement domain ports
- datasources are used by infrastructure port implementations or other infrastructure adapters
- datasources read/write technical storage details such as SQLite rows, files, or raw provider
  payloads

Examples:

```text
infrastructure/db/sqlite_agent_context_datasource.py
  -> SqliteAgentContextDatasource

infrastructure/db/sqlite_run_agent_datasource.py
  -> SqliteRunAgentDatasource

infrastructure/llm/codex/codex_credentials_datasource.py
  -> CodexCredentialsDatasource
```

## Infrastructure Mappers

Mappers convert between infrastructure formats and typed models. They are not ports unless they
explicitly implement a domain port.

```text
packages/skiller/src/skiller/infrastructure/<area>/<tech>_<concept>_mapper.py
```

Mapper modules may expose focused conversion functions. If a mapper is modeled as a class, the
class name must be the PascalCase technology plus the PascalCase concept plus `Mapper`.

Examples:

```text
infrastructure/db/sqlite_run_mapper.py
  -> SqliteRunMapper

infrastructure/llm/codex/codex_mapper.py
  -> Codex mapper functions
```

## Verification Checklist

A naming check should reject:

- a domain port class that does not end in `Port`
- a domain port file that does not end in `_port.py`
- an infrastructure class implementing a domain port without the `Port` suffix
- an infrastructure port implementation file without the `_port.py` suffix
- a datasource class without the `Datasource` suffix
- a datasource file without the `_datasource.py` suffix
- an application import of an infrastructure port implementation or datasource
- a compatibility alias or re-export that hides a naming mismatch
