# Clinic Project Context

Read this first for all `aif-*` skills in this repo.

## Project Facts

- Clinic EMR and operations platform for admin, registrar, doctor, cashier, and lab workflows.
- Backend stack: FastAPI, SQLAlchemy, Pydantic v2, PostgreSQL, Alembic, Redis pub/sub.
- Frontend stack: React 18, Vite, React Router, Axios.
- Test stack: Pytest, Vitest, Playwright, k6.
- Local runtime contour: backend `http://localhost:18000`, frontend `http://localhost:5173`, staging Postgres on `localhost:55432`.
- Vite proxies `/api` and `/ws` to backend `18000`.

## Hard Rules

- PostgreSQL + Alembic are the source of truth. Do not treat SQLite as an operational target.
- Use the layered flow `endpoint -> service -> repository -> DB`.
- Keep controllers thin. Business logic belongs in services.
- Repositories must not import HTTP objects.
- Frontend components must not hardcode backend URLs or role rules.
- Any schema change must go through Alembic.
- Any change touching auth, RBAC, EMR, billing, queue, display, or settings state must preserve auditability and role checks.
- Keep docs and runbooks in sync with runtime, ports, and operator workflow changes.
- If the worktree is dirty, do not revert unrelated user changes.
- `aif-evolve` owns `.ai-factory/evolutions/*`; `aif-loop` owns its own loop state under `.ai-factory/evolution/*`. Never conflate those artifacts.

## Verification Norms

- Backend work should be verified against `18000`.
- Frontend work should be verified against `5173` and the Vite proxy.
- Staging and CI references should distinguish `18080` frontend and `55432` Postgres when relevant.
- Prefer targeted backend tests, frontend tests, or browser smoke evidence over broad speculative checks.
- When persistence or live UI state changes, verify the behavior without relying on a full reload unless that is the intended flow.

## Recurring Drift to Guard Against

- Legacy `8000` defaults are stale; use `18000` for backend verification.
- CORS/origin drift between backend env and Vite dev hosts.
- Input normalization issues for phones, codes, timestamps, and payment values.
- Live-state regressions where the UI only updates after reload.
