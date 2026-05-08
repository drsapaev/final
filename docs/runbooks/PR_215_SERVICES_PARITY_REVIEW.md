# PR #215 Services Endpoint Parity Review

Updated: 2026-05-02 23:11:36 +05:00

## Status

PR #215 still must not resolve `backend/app/api/v1/endpoints/services.py` by simply accepting the replacement-parent branch version.

## Evidence

A fresh isolated temp clone attempted to merge current `origin/main` into `codex/w2a-root-parent-replacement-20260502`.

Conflicts appeared in:

- `backend/app/api/v1/endpoints/messages.py`
- `backend/app/api/v1/endpoints/services.py`

For the services conflict, the branch version is a thinner endpoint layer that delegates CRUD behavior to `ServicesApiService`. Current main keeps more behavior in the endpoint file.

A targeted structural scan found current main behavior that is not present in the branch endpoint or service module:

- `ServiceAuditService`
- `ServiceAuditLog`
- `VisitService`
- `_normalize_service_code_payload`
- `_validate_service_code_prefix_alignment`
- `_should_validate_service_code_alignment`
- `get_allowed_service_code_prefixes`
- `_resolve_queue_group_key`

The service module does include basic CRUD delegation and `_normalize_service_code`, but that is not enough to prove parity with current main.

## Decision

Stop the refresh. Do not push a conflict resolution for `services.py` yet.

## Required Next Slice

Before #215 can be refreshed safely:

1. Decide canonical owner for services validation/audit behavior: endpoint file vs service layer.
2. If service-first remains the goal, move or preserve the current main service-code alignment, audit logging, and visit/delete guards inside the service layer.
3. Add targeted proof for create/update/delete behavior, especially service-code mismatch, audit logging, and visit guard behavior.
4. Retry the #215 merge refresh only after parity is proven.
