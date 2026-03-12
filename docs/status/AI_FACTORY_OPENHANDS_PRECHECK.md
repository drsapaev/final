# AI Factory + OpenHands Precheck

Date: 2026-03-06

## Scope

This precheck covers repository state, local tooling, existing AI setup, and integration blockers for an AI Factory planner plus OpenHands executor model.

## What Was Found

### Repository state

| Area | Finding |
|---|---|
| Git branch | `main` |
| Working tree | Dirty. Existing user changes were present in `frontend/src/components/layout/HeaderNew.jsx`, `frontend/src/pages/Settings.jsx`, and `frontend/src/styles/macos.css`. |
| App topology | Monorepo-style full-stack repo with `backend/`, `frontend/`, `docs/`, `ops/`, `scripts/`, and existing AI metadata. |
| OpenHands setup | No existing `.openhands/` config, no repo-local launcher, no contract format, no handoff docs. |

### Backend stack

| Area | Finding |
|---|---|
| Runtime | Python `3.11.1` available locally |
| Framework | FastAPI (`backend/pyproject.toml`, `backend/requirements.txt`) |
| Data layer | SQLAlchemy 2.x, Alembic, PostgreSQL as declared SSOT, Redis dependency present |
| Domain surface | Large auth/RBAC, queue, EMR, payment, webhook, and AI-assisted endpoint footprint under `backend/app/api/v1/endpoints/` |
| Packaging | `backend/pyproject.toml` plus `backend/requirements.txt`; versions are not fully identical and should be treated as dual sources that need care |

### Frontend stack

| Area | Finding |
|---|---|
| Runtime | Node `22.17.1`, npm `10.9.2` |
| Framework | React 18 + Vite 6 |
| UI libs | MUI 5, Storybook 8, React Router 6, Axios |
| Testing | Vitest `3.2.4`, Playwright `1.57.0`, Testing Library |
| Scope size | Large component surface including auth, payments, queue, EMR, admin, and accessibility tests |

### Test stack

| Area | Finding |
|---|---|
| Backend | Pytest `8.4.1`, coverage enabled in `backend/pytest.ini`, unit/integration/security markers defined |
| Frontend | Vitest with jsdom and Windows-safe single-fork config |
| Browser | Playwright config present with Chromium, Firefox, WebKit, and mobile projects |
| Test footprint | `git ls-files` counted `158` tracked test files across backend and frontend test locations |

### Workflows

Existing GitHub Actions workflows:

- `.github/workflows/ci-cd-unified.yml`
- `.github/workflows/security-scan.yml`
- `.github/workflows/role-system-check.yml`
- `.github/workflows/format-code.yml`
- `.github/workflows/load-testing.yml`
- `.github/workflows/monitoring.yml`

Key unified CI jobs already present:

- `code-quality`
- `frontend-tests`
- `backend-tests`
- `architecture-boundary`
- `frontend-backend-parity`
- `security`
- `docker`
- `integration`
- `load-tests-nightly`
- `dast-zap-nightly`
- `docs`

### Existing docs by domain

| Domain | Examples found |
|---|---|
| Auth / RBAC | `docs/AUTHENTICATION_SYSTEM_FINAL_GUIDE.md`, `docs/ROLES_AND_ROUTING.md`, `docs/ROLE_SYSTEM_PROTECTION.md` |
| Security | `docs/PRODUCTION_SECURITY.md`, `docs/CI_GUARDRAILS.md`, backend security docs and tests |
| Queue | `docs/QUEUE_SYSTEM_ARCHITECTURE.md`, `docs/ONLINE_QUEUE_SYSTEM_GUIDE.md`, queue reports in root and backend |
| Payment | `PAYMENT_SYSTEM_FINAL_REPORT.md`, `backend/WEBHOOK_SYSTEM_GUIDE.md`, payment endpoints/tests |
| EMR | `docs/EMR_USER_GUIDE.md`, `docs/EMR_V2_DOCTOR_GUIDE.md`, EMR endpoints/services/models |
| AI / MCP | `docs/AI_INTEGRATION_GUIDE.md`, `docs/MCP_INTEGRATION_GUIDE.md`, `docs/AI_ARCHITECTURE_RULE.md` |

### Existing AI Factory state

| Area | Finding |
|---|---|
| AI Factory metadata | `.ai-factory/` already exists with `DESCRIPTION.md`, `ARCHITECTURE.md`, `PLAN.md`, `ROADMAP.md`, `patches/`, and `logs/` |
| Agent config | `.ai-factory.json` already exists |
| Installed core AI Factory skills | Present under `.codex/skills/` |
| MCP flags | `.ai-factory.json` currently has `github=false`, `filesystem=false`, `postgres=false`, `chromeDevtools=false` |
| Third-party skill packs | Present under `.agents/skills/` |

### Docker and local dev setup

| Area | Finding |
|---|---|
| App compose | `ops/docker-compose.yml` exists for postgres/backend/frontend |
| Docker CLI | Installed (`docker 28.5.1`, `docker compose v2.40.2`) |
| Docker daemon | Not reachable in this session; `docker image ls` failed because the Linux engine is not running |
| Missing env file | `ops/docker-compose.yml` references `backend/.env.production`, but that file is not present in this repo checkout |
| Local onboarding | `docs/runbooks/LOCAL_DEV_ONBOARDING.md` exists |

## What Already Exists

- AI Factory metadata and baseline architecture docs exist.
- Repo-local skill directories already exist for AI Factory core skills.
- Third-party reusable skills are already present under `.agents/skills/`.
- CI is already acting as a meaningful independent arbiter.
- There is an app-level Docker setup for local backend/frontend/postgres work.

## What Is Missing

- No repo-local OpenHands execution wrapper.
- No contract file standard for planner-to-executor handoff.
- No repo-specific narrow skills for the requested audit/hardening/polish task classes.
- No documented guardrails for bounded autonomous execution.
- No verified AI Factory to OpenHands RPC or API integration.
- No enabled MCP connections in the existing AI Factory config.

## What May Block Integration

1. OpenHands local CLI is not the minimal path here.
   - Host Python is `3.11.1`.
   - `uv` is not installed.
   - Official OpenHands local CLI flow currently expects Python `3.12+`.
2. Docker-based OpenHands is currently blocked by local daemon availability.
   - Docker CLI exists, but the Linux engine was not reachable during precheck.
3. Repo docs include optimistic status reports.
   - Multiple root and domain reports claim `100%`, `production ready`, or similar completion states.
   - Those claims should not be used as automation truth without code and test verification.
4. Existing compose setup has a missing production env file reference.
   - That is unrelated to OpenHands directly, but it is a reproducibility signal worth documenting.
5. The repo is safety-sensitive.
   - Auth, payments, queue, EMR, migrations, secrets, and workflow permissions make unconstrained executor autonomy unsafe.

## Zones To Protect From Over-Autonomous Changes

Protected by default:

- `backend/app/api/v1/endpoints/auth*.py`
- `backend/app/core/auth.py`
- `backend/app/core/security.py`
- `backend/app/core/rbac.py`
- `backend/app/services/payment*`
- `backend/app/repositories/payment*`
- `backend/app/models/payment*`
- `backend/app/api/v1/endpoints/payment*`
- `backend/app/services/queue*`
- `backend/app/repositories/queue*`
- `backend/app/models/online_queue.py`
- `backend/app/api/v1/endpoints/queue*.py`
- `backend/app/services/emr*`
- `backend/app/models/emr*`
- `backend/app/api/v1/endpoints/emr*.py`
- `backend/alembic/**`
- `backend/.env`
- `backend/.secret_key`
- `.secret_key`
- `.github/workflows/**`

## Precheck Conclusion

Foundation work is appropriate.

What is real today:

- AI Factory is already initialized.
- OpenHands is not yet wired into this repo.
- A safe v1 should be contract-driven and human-reviewed.
- Docker GUI execution is the most realistic OpenHands path for this environment once the daemon is available.

What is not confirmed:

- Full AI Factory plus OpenHands automation.
- Any live MCP bridge between planner and executor.
- Reproducible OpenHands execution in this exact session, because Docker engine and LLM credentials were not available for a full launch validation.
