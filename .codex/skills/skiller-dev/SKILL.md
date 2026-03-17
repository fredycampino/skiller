---
name: skiller-dev
description: Apply the preferred Skiller coding style when refactoring or adding code in this repository. Use when editing runtime services, use cases, ports, or supporting tests and you need code that is flat, explicit, contract-driven, and easy to read.
---

# Skiller Dev

Use this skill to keep Skiller code flat, explicit, and easy to maintain.

## Core Rules

- Keep services thin. Orchestrate; do not persist state directly from the service.
- Put state changes and side effects in dedicated use cases.
- Prefer closed contracts with enums for finite domains like statuses and step types.
- Keep result objects minimal. Prefer `status + payload + error` over many optional fields.
- Trust the contract of a use case. Do not add defensive checks for states that should be impossible.
- Prefer one clear error message over many overly specific status variants.

## Read By Need

- For readability and control-flow rules, read `SKILL.md -> references/code-style.md`.
- For architecture boundaries and allowed dependencies, read `SKILL.md -> references/architecture-rules.md`.
- For runtime patterns used in this repo, read `SKILL.md -> references/runtime-patterns.md`.
- For test taxonomy and what counts as unit/integration/e2e here, read `SKILL.md -> references/testing-rules.md`.
- For the general pre-commit checklist used in this repo, read `SKILL.md -> references/pre-commit-checklist.md`.
- For the documented feature and release branch flow of this repo, read `SKILL.md -> references/workflow.md`.
- For functional runtime rules around waiting, resume, and persisted external events, prefer `SKILL.md -> references/runtime-patterns.md`.

## Sandbox Execution

- Do not assume `pytest` is available in the global `PATH`.
- In this repo, run tests with `./.venv/bin/pytest ...`.
- If you prefer activation first, use `source .venv/bin/activate` and then `pytest ...`.
- For ad hoc Python commands with local imports, use `PYTHONPATH=src python3 ...`.
- When reporting verification, include the exact command so the next agent can repeat it without rediscovering the environment.

## Release Workflow

Use the documented repo flow in `references/workflow.md` unless the user says otherwise.
- Treat the `[Agent]`, `[User]`, `[Admin]`, and `[Workflow]` labels in `references/workflow.md` as the source of truth for responsibilities.
- If the environment lacks the required GitHub permissions or tools, report that as a blocker instead of inventing a different flow.

## Default Checklist

- Is the control flow flat?
- Are statuses and types modeled as enums when appropriate?
- Does each use case have one clear responsibility?
- Is the service only coordinating use cases?
- Would a new reader understand the happy path first?
- Are invalid cases reported with one clear message?
- If behavior or step contracts changed, did you review the affected docs, especially `docs/steps/*` and `docs/guia_creacion_skills.md`?
- If the task involves integration or release prep, did you follow `references/workflow.md` instead of an older manual flow?
