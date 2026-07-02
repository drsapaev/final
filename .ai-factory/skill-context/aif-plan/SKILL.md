# `aif-plan` Context

Read `../common/SKILL.md` first.

## Project-Specific Notes

- Plans should reflect the current clinic stack and the modular monolith boundaries from `.ai-factory/ARCHITECTURE.md`.
- For schema work, always include an Alembic migration task and a verification task against PostgreSQL.
- For frontend or browser-visible work, include a browser smoke or Playwright verification task when the flow is user-facing.
- For cross-domain work, call out the affected modules explicitly instead of writing generic plan items.
- Keep plans resume-friendly: short task names, evidence checkpoints, and explicit blockers.
- When a plan touches runtime defaults, note backend `18000`, frontend `5173`, and staging `55432` in the plan context.

