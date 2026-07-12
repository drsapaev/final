# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**⚠️ IMPORTANT:** This file is secondary context. For operational rules, execution modes, and canonical-first discipline, see `AGENTS.md` first. If instructions conflict, prefer the narrower, safer, more canonical rule from `AGENTS.md`.

## ⚠️ MANDATORY: Pre-Deploy Validation

**Before claiming "the system works" or "deployment complete", you MUST run:**

```bash
bash scripts/smoke_test_staging.sh
```

This runs the 10 checks documented in `docs/runbooks/STAGING_VALIDATION.md`:
Sentry, DR drill, AI kill-switch, AI safety contract, arq worker, PII
scrubbing, pre-commit, backend tests, frontend tests.

**You MUST NOT write "it works" or "deployment complete" in any commit, PR,
or chat response unless every check passed.** Patient safety depends on
honest reporting.

See `docs/runbooks/STAGING_VALIDATION.md` for the full checklist with
exact commands and expected outputs.

## Project Overview

This is a **Medical Clinic Management System** built with FastAPI (Python backend) and React (Vite frontend). The system manages patient appointments, queues, EMR (Electronic Medical Records), payments, and specialized medical panels (cardiology, dermatology, dentistry, laboratory).

**Key Features:**
- Role-based access control (Admin, Doctor, Registrar, Cashier, Lab, Patient, cardio, derma, dentist)
- Real-time queue management via WebSocket — **per-doctor queues** (each doctor has their own queue with independent numbers)
- 2FA authentication with blocking flow
- EMR system with AI integration
- Multi-specialty medical panels (cardiology, dermatology, dentistry) + **generic DoctorPanel for new specialties**
- **Extensible specialty system** — new specialties (neurology, endocrinology, etc.) added via admin UI without code changes
- Payment integration (PayMe provider)
- Telegram and Firebase notifications
- GraphQL API support
- PWA capabilities
- QR self-registration — patients select a specific doctor via QR code

**Architecture decisions:**
- See [ADR-001: Queue Ownership & Specialty Architecture](docs/adr/ADR-001-queue-ownership-and-specialty-architecture.md)
- See [Developer Guide: Adding a New Specialty](docs/developer-guides/adding-a-new-specialty.md)
- Queue ownership: `DailyQueue.specialist_id` → `Doctor.id` (per-doctor, not per-specialty)
- Specialty source of truth: `Doctor.specialty` (not `User.role`)
- Specialty display: `QueueProfile` (name, icon, color, QR visibility)

## Execution Mode Selection (from AGENTS.md)

**Before any code changes, classify the task and choose execution mode:**

### Task Classification Modes
- `analysis` - Understand existing code/architecture
- `locate` - Find implementation/docs locations
- `impact` - Understand touched files, tests, docs, risks
- `canonical` - Separate SSOT from legacy/adapters
- `plan` - Create patch checklist
- `dossier` - Curated engineering context
- `handoff` - Strict execution brief for another agent
- `execute` - Only after canonical anchors are clear

### Execution Modes
Before executing any task, choose exactly one:

1. **`direct_execute`**: Local narrow task, root cause known, likely one file, no risky domain, no ownership ambiguity
2. **`gate`**: Risky task, unclear root cause, multi-file impact, ownership ambiguity, scope-creep risk
3. **`gate_known_root_cause`**: Risky task with confirmed root-cause file
4. **`narrow_override`**: Only after gate misroutes twice with explicit basis

### Automatic Strict Mode Triggers

**Automatically use `plan`, `dossier`, or `handoff` before `execute` when touching:**
- Routing canonicalization or route aliases
- Queue fairness, specialist/profile/doctor mapping, or `queue_time`
- Frontend/backend contract alignment
- Telegram integration
- EMR, lab, rollout, evidence packs, go/no-go, production-sensitive behavior
- Any canonical vs legacy ambiguity

### Pre-Execute Gate (for risky tasks)

For `gate` or `gate_known_root_cause` modes, run:

```powershell
cd C:\final\ai\langgraph
.\scripts\run_agent_gate.ps1 "<user task>"

# Or with known root cause:
.\scripts\run_agent_gate.ps1 "<user task>" --known-root-cause "<relative/path.py>"
```

Use `scripts\run_agent_gate.ps1` instead of bare `python` or `py`; it validates Python 3.11+ and falls back around broken `.venv`/PATH launcher state.
For other local Python commands in this Windows checkout, prefer `C:\final\scripts\run_python.ps1` over bare `python` or `py`.
For backend pytest in this Windows checkout, prefer `C:\final\scripts\run_backend_pytest.ps1 <tests...>`.

**Gate Rules:**
- Execute only inside `First-touch files` from gate output
- Treat `Stop conditions` as hard stops
- If gate fails, stop and report instead of editing
- If gate misroutes, retry once with `--known-root-cause`
- Treat `ai/langgraph/EVIDENCE_LIGHTRAG_READINESS.md` as a historical log; do not append routine entries unless explicitly evaluating LightRAG/dev-brain quality.

## Canonical First Discipline

**Before proposing or changing code:**
1. Identify canonical/SSOT sources first
2. Prefer executable source, contract tests, route registries, service layers, migrations
3. Explicitly distinguish canonical from legacy/adapters/compatibility paths
4. **Stop instead of guessing** if canonical vs legacy ownership is unclear

**Canonical Anchors in This Project:**
- Roles: `backend/app/models/role_permission.py` (SINGLE SOURCE OF TRUTH)
- Routes: `frontend/src/routing/routeRegistry.js`
- Service codes: `backend/app/services/service_mapping.py`
- Queue groups: `backend/app/services/service_mapping.py` (QUEUE_GROUPS)
- Auth flow: `backend/app/services/authentication_service.py`

## Safe Patch Slice

**Before first edit, name:**
- Canonical anchors
- Files to read as reference only
- First-touch files allowed for first iteration
- Narrow validation target

**For code changes:**
- Start with smallest safe patch slice
- Touch only first-touch files first
- Do not do opportunistic cleanup
- Do not expand scope without concrete reason and user-visible report

## Development Commands

### Backend (Python/FastAPI)

**Working Directory:** Always run backend commands from `C:\final\backend`

```bash
# Start development server (from backend directory)
cd backend
python run_server.py

# Run tests
python test_role_routing.py
python test_user_management_system.py
python check_system_integrity.py

# Database migrations (if using Alembic)
alembic revision --autogenerate -m "description"
alembic upgrade head

# Create admin user
python app/scripts/ensure_admin.py
```

**API Documentation:** http://localhost:18000/docs (Swagger UI)

### Frontend (React/Vite)

**Working Directory:** `C:\final\frontend`

```bash
# Start development server
npm run dev              # Runs on http://localhost:5173

# Build for production
npm run build

# Preview production build
npm run preview

# Linting
npm run lint             # Fix lint issues
npm run lint:check       # Check only

# Testing
npm run test             # Run Vitest
npm run test:ui          # Vitest UI
npm run test:run         # Run once
npm run test:e2e         # Playwright E2E tests
npm run test:e2e:ui      # Playwright UI mode

# Storybook
npm run storybook        # Run Storybook dev server
npm run build-storybook

# Bundle analysis
npm run analyze
npm run build:analyze
```

### Docker Deployment

```bash
# From ops/ directory
docker compose up --build
docker compose logs -f backend
docker compose logs -f frontend
```

## Architecture Overview

### Backend Structure

**Framework:** FastAPI with SQLAlchemy ORM, Pydantic validation

**Entry Point:** `backend/app/main.py`
- Mounts API routers at `/api/v1`
- Includes WebSocket router for queue updates (`/ws/queue`)
- GraphQL API at `/api/graphql`
- CORS configured via environment variables

**Key Backend Directories:**
- `app/api/v1/endpoints/` - API endpoint modules (100+ endpoint files)
- `app/models/` - SQLAlchemy ORM models
- `app/crud/` - Database operations (CRUD layer)
- `app/core/` - Security, config, roles
- `app/services/` - Business logic services
- `app/ws/` - WebSocket handlers for real-time updates

**Database:** PostgreSQL + Alembic

**Authentication:**
- JWT tokens via `python-jose`
- Password hashing: argon2 (new) + bcrypt (legacy support)
- 2FA with **blocking flow**: `login → pending_2fa_token → verify → access_token`
- Location: `app/core/security.py`, `app/services/authentication_service.py`

**Critical Backend Files:**
- `app/models/role_permission.py` - **SINGLE SOURCE OF TRUTH** for roles
- `app/core/roles.py` - Role enums
- `app/api/v1/api.py` - Main API router that includes all endpoint modules

### Frontend Structure

**Framework:** React 18 with React Router v6, Vite bundler

**Entry Point:** `frontend/src/main.jsx` → `App.jsx`

**Key Frontend Features:**
- **macOS-inspired UI** with custom design system (CSS variables in `styles/macos.css`)
- Theme system with light/dark modes plus custom schemes (vibrant, glass, gradient)
- Code splitting with lazy loading for large pages
- PWA support with install prompts

**Important Frontend Directories:**
- `src/pages/` - Page components (AdminPanel, DoctorPanel, RegistrarPanel, etc.)
- `src/components/` - Reusable UI components
  - `components/auth/` - Authentication forms (**USE LoginFormStyled.jsx, NOT Login.jsx**)
  - `components/medical/` - EMR, medical records
  - `components/ui/macos/` - macOS UI components (Sidebar, Header, Icon)
  - `components/tables/` - Data tables
- `src/contexts/` - React contexts (ThemeContext, AppDataContext)
- `src/api/` - API client with interceptors
- `src/stores/` - State management (auth store)

**Routing:**
- Role-based route protection via `RequireAuth` component
- Soft role checking (doesn't block if no profile)
- AppShell component wraps authenticated routes with macOS header/sidebar

**Theme System:**
- Centralized via `useTheme()` hook - **NEVER import designTokens directly**
- Use helper functions: `getColor()`, `getSpacing()`, `getFontSize()`, `getShadow()`
- Custom color schemes stored in localStorage and applied at app initialization

### Role System

**CRITICAL:** Only use models from `backend/app/models/role_permission.py`

**Available Roles:**
- Admin
- Doctor (general)
- Registrar
- Cashier
- Lab
- Patient
- Specialized: cardio, derma, dentist

**Role Routing:**
- Frontend: `App.jsx` defines role-based routes
- Backend: Role checks in endpoints via dependencies
- Test after changes: `python test_role_routing.py`

### Authentication System

**⚠️ CRITICAL RULES - READ `docs/AUTHENTICATION_LAWS_FOR_AI.md`**

1. **Blocking 2FA Flow:** Never issue `access_token` before 2FA verification
2. **Single Role Source:** Use ONLY `app/models/role_permission.py`
3. **Password Hashing:** argon2 for new passwords, maintain bcrypt compatibility
4. **Login Form:** Use `LoginFormStyled.jsx` as primary, NOT `Login.jsx`
5. **Protected Users:** Never delete: admin, registrar, doctor, cardio, derma, dentist

**Authentication Flow:**
```
1. POST /api/v1/authentication/login
   → Returns: pending_2fa_token (if 2FA enabled) OR access_token (if 2FA disabled)

2. POST /api/v1/2fa/verify
   → Input: pending_2fa_token + verification code
   → Returns: access_token + refresh_token
```

### Real-Time Features

**WebSocket Endpoints:**
- `/ws/queue` - Queue updates for display boards and panels
- `/ws/dev-queue` - Development queue endpoint

**Usage:** See `backend/app/ws/queue_ws.py` for implementation patterns

## Important Development Guidelines

### Code Style

**Python (Backend):**
- Follow PEP 8
- Use type hints for all functions
- Use async/await for I/O operations
- Pydantic models for validation
- Black formatter (line length 88)
- Import order: isort with black profile

**JavaScript/React (Frontend):**
- Functional components with hooks
- ESLint for linting (`npm run lint`)
- Avoid direct CSS class manipulation - use theme system

### Medical Data Compliance

- All medical operations must include audit logging
- Patient data requires permission checks
- Transactions required for critical medical operations
- Follow patterns in existing medical endpoints
- Support Russian language (primary user base)

### Testing Requirements

**Backend:**
```bash
# Always run these tests after authentication/role changes
python test_role_routing.py
python test_user_management_system.py
python check_system_integrity.py
```

**Frontend:**
```bash
npm run test              # Unit tests
npm run test:e2e          # E2E tests
npm run lint:check        # Lint check
```

**Multi-user scenarios:** Clinic systems have concurrent user access patterns - always test with multiple simultaneous users

**Validation Discipline (from AGENTS.md):**
- After changes, run the narrowest relevant validation first
- Prefer targeted tests, contract checks, smoke checks over broad unrelated suites
- Do not run heavy checks without a reason
- Report exactly what ran, what passed/failed, and what was not checked

## Stop Conditions (from AGENTS.md)

**Stop and report instead of continuing silently if:**
- Canonical vs legacy conflict is unclear
- Required edits leave the first safe patch slice
- Frontend/backend ownership is not obvious
- No clear verification target exists
- Scope begins to spread across unrelated areas
- Contract ambiguity appears
- A policy, product, rollout, or runtime behavior decision is needed

## Execute Response Format (from AGENTS.md)

**For completed `execute` tasks, answer with:**
- `Changed` - What files were modified
- `Why` - Reason for changes
- `Validation run` - What tests/checks were run
- `Result` - Pass/fail status
- `Scope check` - Did we stay within boundaries?
- `Stop conditions hit` - Any stop conditions encountered?
- `Next smallest step` - What's the next incremental step?

For risky tasks that should not execute yet, output `plan`, `dossier`, or `handoff` instead.

### API Integration

- RESTful principles at `/api/v1/*`
- GraphQL available at `/api/graphql`
- Use proper HTTP status codes
- Include input validation (Pydantic schemas)
- Rate limiting applied
- OpenAPI/Swagger documentation auto-generated at `/docs`

### File Operations

- Medical document uploads must include virus scanning and format validation
- Follow patterns in `backend/app/api/v1/endpoints/file_*.py`
- File storage handled via `backend/app/crud/file_system.py`

### Database Operations

- Use SQLAlchemy ORM
- Alembic for migrations (if needed)
- Transactions for critical operations
- Audit logging for medical data
- Database indices for query optimization

## Common Pitfalls to Avoid

1. **DON'T** bypass the blocking 2FA flow
2. **DON'T** create duplicate role models outside `role_permission.py`
3. **DON'T** use `Login.jsx` - use `LoginFormStyled.jsx`
4. **DON'T** import designTokens directly - use theme hooks
5. **DON'T** run backend commands from root directory - always use `backend/`
6. **DON'T** hardcode secrets - use environment variables
7. **DON'T** skip tests after authentication/role changes
8. **DON'T** mix password hashing schemes
9. **DON'T** break backward compatibility with existing API endpoints
10. **DON'T** commit sensitive files (.env, credentials.json)
11. **DON'T** introduce unrelated edits or opportunistic refactoring (from AGENTS.md)
12. **DON'T** reintroduce SQLite-first defaults - PostgreSQL + Alembic are SSOT
13. **DON'T** edit generated evidence in `output/`, `test-results/`, `storage/` unless task explicitly asks
14. **DON'T** preserve user changes in dirty worktree - never revert unrelated work

## Domain Guardrails (from AGENTS.md)

### Routing
- Start from routing SSOT: `frontend/src/routing/routeRegistry.js`
- Verify route contract/snapshot tests before broad cleanup
- Do not mass-edit unrelated routes in first slice

### Queue System
- **Protect fairness invariants and `queue_time`**
- Inspect queue-related tests first
- Avoid SSOT drift between profile, specialist, doctor, queue, and online queue mapping layers
- Queue groups defined in: `backend/app/services/service_mapping.py` (QUEUE_GROUPS)

### Telegram Integration
- Consider both frontend manager files and backend Telegram endpoint/service contracts
- Do not infer integration behavior from frontend text alone
- Keep first patch slice narrow even for mixed frontend/backend changes
- Patterns: `backend/app/api/v1/endpoints/telegram_*.py`

### EMR, Lab, Rollout-Sensitive Areas
- Prefer canonical runbooks, contract docs, migrations, evidence docs
- Do not infer production-critical behavior from random overview docs
- **Stop on ambiguity rather than improvising**
- All medical operations must include audit logging
- Patient data requires permission checks
- Transactions required for critical medical operations

### Service Management (Recently Enhanced)
- Service audit log: `backend/app/models/service_audit.py`
- Service codes SSOT: `backend/app/services/service_mapping.py`
- Batch operations: `/services/admin/batch-update` endpoint
- All service changes are logged with user, timestamp, and field-level diffs
- Service code validation: prefix must match category/queue group

## Key Documentation Files

**Must Read Before Authentication Work:**
- `docs/AUTHENTICATION_LAWS_FOR_AI.md` - **MANDATORY** laws for AI agents
- `docs/AUTHENTICATION_SYSTEM_FINAL_GUIDE.md` - Complete auth system guide
- `docs/ROLE_SYSTEM_PROTECTION.md` - Role system protection rules

**Other Important Docs:**
- `.cursorrules` + `.cursor/rules/*.mdc` - Project-specific rules
- `docs/AI_INTEGRATION_GUIDE.md` - AI feature integration
- `docs/MCP_INTEGRATION_GUIDE.md` - Model Context Protocol integration
- `docs/QUEUE_SYSTEM_IMPROVEMENTS.md` - Queue system architecture
- `ops/README.md` - Docker deployment

## Environment Variables

**Backend Key Variables:**
- `DATABASE_URL` - Database connection (example: PostgreSQL via `postgresql+psycopg://clinic:<db_password>@localhost:5432/clinicdb`)
- `SECRET_KEY` - JWT secret
- `API_V1_STR` - API prefix (default: `/api/v1`)
- `CORS_ORIGINS` - Allowed CORS origins
- `CORS_ALLOW_ALL` - Allow all origins (dev only)
- `ADMIN_USERNAME`, `ADMIN_PASSWORD` - Default admin credentials

**Frontend:**
- API endpoint configured in `src/api/interceptors.js`
- Uses `http://localhost:18000` for backend in dev mode

## Project-Specific Conventions

### Never Rollback Working Code
- Always treat local changes as source of truth
- Compare with current version (diff) before rewriting files
- Propose merge solutions instead of overwriting
- Ask user before large refactorings

### Russian Language Support
- All user-facing text must support Russian
- Backend runs from `C:\final\backend` directory with `python run_server.py`
- Maintain backward compatibility with existing APIs

### Integration Patterns
- Payment webhooks: Follow patterns in `backend/app/api/v1/endpoints/payment_webhook.py`
- Telegram integration: See `backend/app/api/v1/endpoints/telegram_*.py`
- WebSocket: Follow patterns in `backend/app/ws/`

## Specialized Medical Panels

The system includes specialized unified panels with their own routing:

- **Cardiologist Panel** (`/cardiologist`) - Cardiology examinations, ECG
- **Dermatologist Panel** (`/dermatologist`) - Dermatology, photo archive
- **Dentist Panel** (`/dentist`) - Dental chart, treatment plans, prosthetics
- **Lab Panel** (`/lab-panel`) - Laboratory tests and results

Each panel uses URL parameters (`?tab=`) for internal navigation and includes specialized medical tools.

## GraphQL API

GraphQL endpoint available at `/api/graphql` with schema explorer in admin panel (`?section=graphql-explorer`).

## Recent Enhancements (2026-04-14)

### Service Management System Improvements

**Audit Logging:**
- Full history tracking for all service changes (create, update, delete, activate/deactivate)
- Field-level change tracking with old → new value diffs
- User attribution, timestamps, IP addresses, comments
- Database: `service_audit_logs` table (migration: `0022_service_audit_log`)
- Backend: `ServiceAuditLog` model, `ServiceAuditService` service
- Frontend: `ServiceAuditHistory` component with expandable change details
- API: `GET /services/{id}/history`, `GET /services/admin/audit/recent`

**Optimistic UI Updates:**
- Immediate UI updates without full page reload
- Automatic rollback on server errors
- Better UX with instant feedback

**Change Preview (Diff):**
- Visual preview of all changes before saving
- Side-by-side comparison: old value (strikethrough) → new value (green)
- Highlights important changes (price, code, name, active status)
- Component: `ServiceChangesPreview`

**Batch Operations:**
- Mass edit multiple services simultaneously
- Select services via checkboxes
- Update common fields: price, category, duration, active status, etc.
- Detailed success/failure reporting
- All batch changes logged in audit history
- API: `POST /services/admin/batch-update`
- Component: `ServiceBatchEdit`

**Key Files:**
- Backend: `app/api/v1/endpoints/services.py`, `app/services/service_audit_service.py`, `app/models/service_audit.py`
- Frontend: `components/admin/ServiceCatalog.jsx`, `components/admin/ServiceAuditHistory.jsx`, `components/admin/ServiceChangesPreview.jsx`, `components/admin/ServiceBatchEdit.jsx`
- Migration: `alembic/versions/0022_service_audit_log.py`

## Local Dev-Brain Commands (from AGENTS.md)

From `C:\final\ai\langgraph`:

```powershell
# Execution gate for risky tasks
.\scripts\run_agent_gate.ps1 "<task>"
.\scripts\run_agent_gate.ps1 "<task>" --known-root-cause "<path>"
```

Historical `dev_brain.py`, `planner_smoke.py`, `dossier_smoke.py`, and `handoff_smoke.py` commands are not verified in this checkout. Use the AGENTS.md plan/dossier/handoff rules directly unless those files are restored and validated.

Use `handoff` as the default input contract for the next agent when a real code change is risky or multi-file.

## Notes

- Backend server must always run from `C:\final\backend` directory
- Frontend dev server runs on port 5173, backend on 18000
- Database source of truth: PostgreSQL + Alembic (never SQLite)
- **Execution discipline:** Follow AGENTS.md for canonical-first, safe patch slice, and stop conditions
- **For risky tasks:** Use `agent_gate.py` before editing
- **LightRAG evidence:** Treat `ai/langgraph/EVIDENCE_LIGHTRAG_READINESS.md` as historical; do not append routine risky-task entries.
- Recent work: Service management enhancements (audit log, batch ops, optimistic updates, change preview)
