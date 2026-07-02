# `aif` Context

Read `../common/SKILL.md` first.

## Project-Specific Notes

- This repo is a clinic platform, so setup should prioritize FastAPI, React/Vite, PostgreSQL, Alembic, Redis, Pytest, Vitest, and Playwright.
- Confirm runtime defaults against `backend/run_server.py` and `frontend/vite.config.js` before suggesting ports or proxy targets.
- Prefer the existing `.ai-factory/` files as project truth:
  - `.ai-factory/DESCRIPTION.md`
  - `.ai-factory/ARCHITECTURE.md`
  - `.ai-factory/RULES.md`
  - `.ai-factory/ROADMAP.md`
- If a setup step would reintroduce SQLite-first guidance, reject it.

