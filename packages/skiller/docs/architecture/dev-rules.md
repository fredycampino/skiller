# Development Rules

These rules apply to any proposed design, implementation plan, code change, or final result.

## Mandatory Review

Before work is considered done, review it against:

- [`architecture.md`](architecture.md)
- [`code-style.md`](code-style.md)
- [`naming-style.md`](naming-style.md)

The review must explicitly look for:

- architecture violations
- unnecessary compatibility paths
- dead code
- weak naming
- misplaced responsibilities
- tests that do not prove useful behavior

If a finding is intentionally accepted, state why and keep the exception local to the change.
