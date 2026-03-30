# AGENTS.md

> Project map for AI agents. Keep this file aligned with the tracked project structure.

## Project Overview
Clinic Management System: a full-stack EMR and clinic operations platform for admin, registrar, doctor, cashier, lab, queue, and billing workflows.

## Tech Stack
- Backend: Python 3.11, FastAPI, SQLAlchemy, Pydantic v2
- Frontend: JavaScript/JSX, React 18, Vite, React Router
- Database: PostgreSQL
- Migrations: Alembic
- Testing: Pytest, Vitest, Playwright, k6
- Realtime/Infra: Redis pub/sub and WebSocket broadcast

## Project Structure
```text
backend/
  app/
    api/v1/endpoints/   # FastAPI route handlers by domain
    services/           # business logic
    repositories/       # persistence layer
    models/             # SQLAlchemy models
    schemas/            # Pydantic contracts
    core/               # config, security, shared infra
    db/                 # session/engine setup
    ws/                  # websocket channels
  alembic/versions/     # database migrations
  tests/                # backend unit and integration tests
  run_server.py         # local backend entry point (:18000)
frontend/
  src/
    pages/              # route-level screens
    components/         # reusable UI by domain
    api/                # HTTP clients
    hooks/              # shared React hooks
    utils/              # helper modules
  e2e/                  # Playwright end-to-end tests
  vite.config.js        # dev server/proxy config (:5173 -> :18000)
docs/
  architecture/
  runbooks/
  archives/
.ai-factory/
  DESCRIPTION.md
  ARCHITECTURE.md
  RULES.md
  ROADMAP.md
  patches/
  evolutions/
  skill-context/
.codex/skills/
.github/workflows/
ops/
scripts/
output/                 # generated evidence/artifacts
test-results/            # generated test output
storage/                # runtime files/data
```

## Key Entry Points
| File | Purpose |
|---|---|
| `backend/app/main.py` | FastAPI app composition and router wiring |
| `backend/run_server.py` | Local backend launcher on port 18000 |
| `frontend/src/main.jsx` | React bootstrap |
| `frontend/src/App.jsx` | Root frontend composition |
| `frontend/vite.config.js` | Vite dev server and API/WebSocket proxy |
| `package.json` | root scripts and workspace entry |
| `.ai-factory/DESCRIPTION.md` | project context and runtime defaults |
| `.ai-factory/ARCHITECTURE.md` | architecture decisions and boundaries |

## Documentation
| Document | Path | Purpose |
|---|---|---|
| README | `README.md` | project landing page |
| Claude guide | `CLAUDE.md` | agent workflow and runtime notes |
| AI/MCP quickstart | `QUICKSTART_AI_MCP.md` | local AI/MCP startup guide |
| Agent setup | `AI_AGENT_SETUP.md` | auth-focused agent setup |
| Docs landing | `docs/README.md` | documentation index |
| Local staging runbook | `docs/runbooks/LOCAL_STAGING_ACCEPTANCE_RUNBOOK.md` | acceptance flow for the current contour |
| Postgres guide | `docs/POSTGRESQL_PRODUCTION_GUIDE.md` | database operations |
| Plan checklist | `docs/PLAN_CHECKLIST.md` | milestone tracker |

## AI Context Files
| File | Purpose |
|---|---|
| `AGENTS.md` | structural map for AI agents |
| `.ai-factory/DESCRIPTION.md` | project specification and runtime context |
| `.ai-factory/ARCHITECTURE.md` | architecture rules and boundaries |
| `.ai-factory/RULES.md` | project rules and conventions |
| `.ai-factory/ROADMAP.md` | strategic roadmap |
| `.mcp.json` | project MCP server configuration |
| `CLAUDE.md` | editor/agent guidance for this repo |

## Agent Rules
- Treat `.ai-factory/DESCRIPTION.md` and `.ai-factory/ARCHITECTURE.md` as the source of truth for project context.
- Verify runtime ports against `backend/run_server.py` and `frontend/vite.config.js` before changing docs or setup files.
- Keep PostgreSQL + Alembic as the database source of truth.
- Avoid reintroducing SQLite-first defaults in docs or setup templates.
- Leave generated evidence in `output/`, `test-results/`, and `storage/` alone unless the task is explicitly about artifacts.
- Use project-level MCP settings from `.mcp.json`; do not edit `.claude/settings.local.json` for shared project config.
