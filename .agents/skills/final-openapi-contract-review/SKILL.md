---
name: final-openapi-contract-review
description: Project-specific workflow for OpenAPI, API DTO, schema-shape, and frontend/backend contract review in this FastAPI + React clinic system. Use when adding or changing API endpoints, /api/v1/ui screen/read-model DTOs, generated OpenAPI shape, frontend API adapters, contract tests, or schema assertions.
---

# Final OpenAPI Contract Review

Use this skill when an API change needs a provable contract, especially before or during BFF-lite `/api/v1/ui/*` read-model work.

This is a local repo-specific contract discipline. External OpenAPI/Speakeasy-style guidance may inspire the approach, but the authoritative evidence is this repo's FastAPI app, Pydantic schemas, tests, and frontend API usage.

## Context Gate

Read the smallest relevant set:

- `AGENTS.md`
- `.ai-factory/ARCHITECTURE.md`
- backend endpoint, service, schema, and test files for the changed route
- frontend API adapter or screen consuming the route
- `backend/tests/test_openapi_contract.py`
- related frontend contract/API tests under `frontend/src/api` or screen tests

For `/api/v1/ui/*` endpoints, also use `final-bff-lite-read-model`.
For frontend-owned business decisions, use `final-ssot-contract-repair` first.

## Contract Checklist

For every route or DTO change, prove:

- The route is published in FastAPI OpenAPI unless intentionally private.
- Request and response schemas are explicit Pydantic models, not loose dicts where a DTO is needed.
- Required, nullable, enum/status, list, pagination, and error shapes are intentional.
- Sensitive fields are redacted from OpenAPI-visible response models.
- Operation IDs are stable and duplicate-free.
- Frontend adapters consume the documented shape without fallback guessing.
- Tests cover the exact schema shape the frontend relies on.

## UI Read-Model DTO Rules

For BFF-lite screen endpoints:

- Name schemas under `backend/app/schemas/ui/` when added.
- Keep DTOs read-only unless the route is explicitly a command wrapper.
- Include `available_actions` only when calculated by core services.
- Include canonical IDs and record types from backend sources; do not force React to infer them.
- Include display-safe status facts, but keep state transitions in core services.
- Prefer one focused screen DTO over broad generic dashboard payloads.

## Validation Targets

Prefer narrow checks:

- `backend/tests/test_openapi_contract.py`
- route-specific backend pytest
- frontend API adapter tests
- component/screen tests using realistic DTO fixtures
- OpenAPI duplicate operation ID check

If a route is security-sensitive, also prove auth/role behavior and redaction.

## Output

Report:

- Route or DTO reviewed
- Contract source of truth
- OpenAPI visibility
- Schema-shape assertions
- Frontend consumer impact
- Tests run or proposed
- Contract gaps before merge
