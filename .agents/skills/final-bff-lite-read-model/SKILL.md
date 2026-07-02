---
name: final-bff-lite-read-model
description: Project-specific workflow for designing or implementing BFF-lite screen/read-model endpoints inside the existing FastAPI backend after SSOT contract repair. Use for FastAPI UI endpoints, screen APIs, read-model services, Registrar workbench, Queue join, Queue board, Lab workbench, Admin audit/dashboard, Telegram admin dashboard, or questions about whether to add BFF-lite versus a separate BFF service.
---

# Final BFF-Lite Read Models

Use this skill only after checking for frontend/backend SSOT leaks. BFF-lite in this project means screen/read-model endpoints inside the existing FastAPI backend, not a separate service and not a second source of truth.

The default decision is:

1. Repair SSOT contract leaks first.
2. Add narrow read-only screen models only where repo evidence shows React is doing expensive or fragile view assembly.
3. Do not create a separate BFF service unless there is strong evidence of multiple independent clients, divergent release cadence, microservice aggregation, or heavy caching requirements.

## Context Gate

Read the smallest relevant set:

- `AGENTS.md`
- `.ai-factory/ARCHITECTURE.md`
- `.ai-factory/DESCRIPTION.md`
- `.ai-factory/RULES.md`
- relevant frontend screen and API usage
- relevant backend endpoint, service, schema, model, and tests
- existing OpenAPI/contract tests if present

If command behavior is involved, switch to `final-ssot-contract-repair` first.

## Project Reality: final

`final` currently does not have a `ui` backend read-model layer:

- No `backend/app/api/v1/endpoints/ui/` package
- No `backend/app/schemas/ui/`
- No `backend/app/services/read_models/`
- No `api_router.include_router(..., prefix="/ui", ...)` in `backend/app/api/v1/api.py`

Existing endpoints already do several read-model-like aggregations and are the first place to reuse before adding `/api/v1/ui/*`:

- `backend/app/api/v1/endpoints/qr_queue.py`
  - `/queue/available-specialists`
  - `/queue/qr-tokens/{token}/info`
  - `/queue/join/start`
  - `/queue/join/complete`
  - `/queue/status/{specialist_id}`
- `backend/app/api/v1/endpoints/registrar_integration.py`
  - `/registrar/services` (already groups services and applies routing hints)
  - `/registrar/doctors`
  - `/registrar/queues/today`
- `backend/app/api/v1/endpoints/board.py`
  - `/board/state`
- `backend/app/api/v1/endpoints/queues.py`
  - `/stats`

Frontend currently assembles multiple requests on several screens:

- `frontend/src/pages/QueueJoin.jsx` combines public profiles + specialists + token info + join session.
- `frontend/src/pages/DisplayBoardUnified.jsx` combines `/queues/stats` and `/board/state`.
- `frontend/src/pages/RegistrarPanel.jsx`, `CardiologistPanelUnified.jsx`, `DermatologistPanelUnified.jsx`, `DentistPanelUnified.jsx`, `LabPanel.jsx` each load many registrar/queue artifacts with separate calls.

Rule for this project: do not add read-model endpoints just to “align architecture”; start only when frontend orchestration is clearly fragile, duplicated, or error-prone and existing canonical routes cannot be safely extended.
## Allowed Read-Model Responsibilities

`/api/v1/ui/*` endpoints may:

- Aggregate existing backend resources for one screen.
- Filter, redact, and shape data for display.
- Provide stable DTOs for React pages.
- Sort display rows using backend-owned facts.
- Expose `available_actions` calculated by core services.
- Normalize labels or lightweight display metadata when backed by canonical data.

They must not:

- Own queue fairness/order/status transitions.
- Own EMR locking, signing, amendment, or revision rules.
- Own lab finalization, template immutability, analyte/reference range rules.
- Own payment state transitions.
- Own auth, role, permission, or audit write policy.
- Own Telegram token, webhook secret, staff-link, or action authorization policy.
- Mutate durable state unless explicitly designed as a command wrapper around a core service.

## Recommended Shape

Prefer this structure when adding BFF-lite:

```text
backend/app/api/v1/endpoints/ui/
backend/app/schemas/ui/
backend/app/services/read_models/
```

Endpoint naming:

- `GET /api/v1/ui/registrar/workbench`
- `GET /api/v1/ui/queue/join/{token}`
- `GET /api/v1/ui/queue/board`
- `GET /api/v1/ui/lab/workbench`
- `GET /api/v1/ui/admin/audit-dashboard`
- `GET /api/v1/ui/admin/telegram-dashboard`

Only add endpoints that map to a real screen and repo evidence.

## Design Workflow

1. Prove the screen has a real aggregation problem: multiple API calls, duplicated status normalization, fragile client joins, or large React workflow assembly.
2. Prove command/SSOT leaks have been repaired or are out of scope.
3. Define one screen DTO with explicit read-only semantics.
4. Reuse existing services/facades/repositories; do not query across domains ad hoc from the endpoint.
5. Add Pydantic schemas under `schemas/ui` for DTO shape.
6. Add backend tests for DTO shape, redaction, ordering, and permissions.
7. Simplify the frontend page by replacing orchestration with one API call while preserving presentation-only state.

## First-Slice Preference

Start with one high-value read-only screen:

- Registrar workbench after record/payment/queue command contract repair.
- Queue join initial model if QR/profile/specialist/wait-state assembly is unstable.
- Admin service catalog if service/category/doctor/department/queue-profile joins remain frontend-heavy.

Do not start with EMR, lab finalization, payment transition, setup/activation, or Telegram command mutation surfaces.

## Output

For architecture/design tasks, report:

- Screen and evidence
- Current frontend orchestration
- Proposed endpoint and DTO responsibility
- Core services that remain SSOT
- Tests and OpenAPI/contract proof
- Rollback path

For implementation tasks, include the `AGENTS.md` execute response fields and the narrow validation commands run.
