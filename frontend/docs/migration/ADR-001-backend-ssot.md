# ADR-001: Backend = SSOT for domain types

**Date:** 2026-07-17
**Status:** Accepted

## Context

The clinic-frontend project consumes a FastAPI backend that exposes
~731 OpenAPI schemas across ~997 paths. Without a single source of
truth for domain types (User, Patient, Appointment, roles, etc.),
the frontend would need to manually maintain TypeScript interfaces
that mirror the backend — a discipline that fails under time pressure
and produces silent drift.

## Decision

All domain types are generated from `backend/openapi.json` via
`openapi-typescript`. The generated file lives at
`src/types/generated/api.ts` and is treated as read-only (see ADR-002).
Frontend code imports domain types from `src/types/api.ts`, which
re-exports the generated types with convenient aliases.

## Consequences

**Positive:**
- Frontend types update automatically when backend changes —
  run `npm run generate:api-types` after pulling backend changes.
- CI gate `generate:api-types:check` fails if generated types are
  stale, preventing "forgot to regenerate" drift.
- No manual sync discipline required.

**Negative:**
- Generated file is 75K lines (2.3 MB) — large but tree-shakeable.
- `openapi-typescript` requires `--legacy-peer-deps` due to TS 6
  peer dep mismatch (see D-004). Temporary — re-evaluate when upstream
  supports TS 6.

## Alternatives considered

1. **Manual typing** — rejected. Requires sync discipline that fails
   under time pressure. Drift between frontend and backend types
   would be silent and dangerous.

2. **GraphQL codegen** — not applicable. Backend is REST/FastAPI,
   not GraphQL.

3. **tRPC** — would require backend rewrite. Out of scope.

## References

- [openapi-typescript](https://github.com/drwpow/openapi-typescript)
- `scripts/generate-api-types.sh` — generation pipeline
- `src/types/generated/api.ts` — generated output (read-only)
- `src/types/api.ts` — re-exports + aliases
