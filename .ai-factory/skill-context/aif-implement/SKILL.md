# `aif-implement` Context

Read `../common/SKILL.md` first.

## Project-Specific Notes

- Always load the active plan plus `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`, and `.ai-factory/RULES.md` before editing.
- Follow `endpoint -> service -> repository -> DB` for backend changes. Do not bypass repositories or add ad-hoc ORM logic in endpoints.
- If a backend change alters schema, ship the Alembic migration in the same change.
- If a frontend change touches API or realtime calls, verify it against the Vite proxy path to backend `18000`.
- When a user-visible flow changes persistence or live state, add a focused regression test or browser smoke and keep the evidence in the patch or log.
- Update docs/runbooks when startup commands, ports, or operator steps change.
- For admin, billing, queue, display, or EMR work, preserve audit logging and role checks.

