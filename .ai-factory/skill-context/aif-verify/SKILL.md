# `aif-verify` Context

Read `../common/SKILL.md` first.

## Project-Specific Notes

- Verify against the active plan plus `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`, and `.ai-factory/RULES.md`.
- Treat backend `18000`, frontend `5173`, and staging Postgres `55432` as the expected local contour unless the plan says otherwise.
- Do not modify context files during verification unless explicitly asked to fix them.
- When possible, support verdicts with tests, CI output, or browser smoke evidence.

