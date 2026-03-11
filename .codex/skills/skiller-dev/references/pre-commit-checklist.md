# Pre-Commit Checklist

## Goal

- The change solves one clear thing.
- The commit does not mix unrelated work without a reason.

## Code

- The touched code compiles.
- Contracts are coherent.
- Old names or stale concepts are not left behind.
- No personal paths or machine-local assumptions leak into the repo.

## Tests

- The right test level covers the change.
- Do not add redundant tests.
- If a scenario is already covered in `integration`, do not duplicate it in `e2e`.
- `e2e` tests must justify their cost.

## Tree Hygiene

- No `__pycache__`
- No temporary files
- No deleted tests half-replaced by new ones
- No stale references to removed folders or old taxonomy

## Docs

- Update only the docs that really changed.
- If the change alters step behavior or visible runtime contracts, review and update `docs/steps/*` and `docs/guia_creacion_skills.md`.
- Do not duplicate living rules across many files.
- Keep stable rules in the skill references when possible.
- If you detect duplicated rules across skill files, docs, or checklists, prefer consolidating them into one stable source and leave only short pointers elsewhere.

## Operational Risk

- Call out any manual step the user must know.
- Example: "recreate the DB because the schema changed".

## Final Check

- `git status` is understandable.
- The commit can be explained in one sentence.
