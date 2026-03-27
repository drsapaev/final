# `aif-docs` Context

Read `../common/SKILL.md` first.

## Project-Specific Notes

- Treat `README.md` as the landing page and `docs/` as the detailed runbook/reference layer.
- Keep README and runbooks aligned with the current clinic stack, ports, and local staging contour.
- Use the verified runtime contour in examples: backend `18000`, frontend `5173`, and staging Postgres `55432`.
- When operator steps, backend startup, proxying, database flow, or deployment flow changes, update the docs in the same change.
- Keep terminology consistent: Postgres/Alembic source of truth, modular monolith, role-based workflows.
- Replace stale `8000` or SQLite-first guidance with the current verified setup whenever it appears.
