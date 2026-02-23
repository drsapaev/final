# Interoperability and Multi-Clinic Scale (Baseline)

## Goal

Prepare the platform for external ecosystem integrations and safe branch-level isolation without splitting the monolith.

## What Is Implemented

- External integration access now goes through a stable gateway service:
  - `backend/app/services/interoperability_gateway_service.py`
- Contract interfaces for integration registry and provider capabilities:
  - `backend/app/domain/contracts/interoperability_contracts.py`
- Integrations API endpoints now consume the gateway contract instead of concrete provider classes:
  - `backend/app/services/integrations_api_service.py`
- Tenant scope utilities for branch-aware request context resolution:
  - `backend/app/core/tenant_scope.py`
- Feature-flagged tenant-scope enforcement middleware for high-risk write routes:
  - `backend/app/middleware/tenant_scope_middleware.py`
  - config keys in `backend/app/core/config.py`:
  - `TENANT_SCOPE_ENFORCE_WRITES`
  - `TENANT_SCOPE_WRITE_PREFIXES`

## Adapter Contract Surface

- Registry contract:
  - list available integrations,
  - fetch integration by type,
  - verify patient across all configured providers.
- Capability contracts:
  - DMED-specific: patient history,
  - eGOV-specific: benefits,
  - insurance-specific: authorization, claim submit, claim status.

This keeps endpoint/business code decoupled from provider implementation classes.

## Branch Isolation Strategy

Use a single deterministic source for branch scope with clear precedence:

1. Header `X-Branch-ID` (explicit request scope)
2. Query parameter `branch_id` (operation scope)
3. User-bound branch fallback (identity scope)

`tenant_scope.resolve_tenant_scope(...)` implements this precedence and validates positive integer branch IDs.

## Rollout Plan

1. Wire `TenantScope` resolution into selected high-risk write endpoints (`billing`, `queue`, `emr`) behind a feature flag.
   - Status: baseline implemented via middleware guard over write methods (`POST/PUT/PATCH/DELETE`) and configurable protected prefixes.
2. Add repository helpers that require branch scope for branch-owned models.
3. Expand integration contract tests with provider stubs and failure-mode matrix.
4. Add CI guard to fail on direct imports of concrete integration providers from API layer.

## Guardrails

- Provider capability mismatch returns explicit `503` contract errors.
- Missing branch scope can be made hard-fail via `require_branch_scope(...)` when endpoint is marked branch-required.
- Verbose structured logs include request and integration context for incident triage.
