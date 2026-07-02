[<- Previous Page](PROJECT_AUDIT.md) | [Back to README](../README.md) | [Next Page ->](ARCHITECTURE.md)

# Recovery Plan

Implementation source of truth: `.ai-factory/PLAN.md`

## Phase Status

| Phase | Status | Evidence |
|---|---|---|
| Stop and secure | Mostly complete for identified P0s | Tasks 6-12 |
| Critical contracts | Partially complete | Tasks 13-18 |
| UX-visible recovery | Started | Task 19 |
| Developer docs | Started | Task 20 |
| Docs/AIF alignment | Current | Task 21 |
| Full verification | Pending | `/aif-verify --strict` |

## Completed High-Impact Work

- Canonical login now targets the 2FA-aware path.
- Fallback auth is disabled by default.
- Payment webhook processing failures use retryable HTTP errors.
- Simple upload is behind explicit configuration and validates basic file metadata.
- Internal demo routes require `VITE_ENABLE_INTERNAL_DEMO=1`.
- Queue SSOT contract coverage was added.
- Visit read RBAC was tightened.
- Telegram webhook secret validation now fails closed in patched webhook surfaces.
- Alembic revision chain is linear.
- AI routes now have stronger RBAC and visible draft-only notices.
- General doctor panel no longer displays fake patients or fake appointments.

## Next Recovery Steps

1. Finish docs alignment and run `/aif-verify --strict`.
2. Fix verification findings through `/aif-fix`.
3. Run `/aif-security-checklist`.
4. Run `/aif-review`.
5. Prove clean PostgreSQL `alembic upgrade head` on a disposable target.

## Production-Ready Criteria

- Auth and RBAC tests cover real frontend login paths and protected data access.
- Payment callbacks have canonical provider URLs, signature validation, idempotency, and reconciliation tests.
- Upload surfaces are either disabled or backed by validated storage and scan policy.
- AI remains draft-only with human approval and configured-provider fallback behavior.
- Telegram webhook and notification flows have secret validation, retry/outbox behavior, and PHI-safe messaging.
- Alembic upgrade is proven on a disposable PostgreSQL database.
- Deployment docs and rollback/backup runbooks match the actual runtime.

## See Also

- [Project Audit](PROJECT_AUDIT.md)
- [Deployment](DEPLOYMENT.md)
- [Testing](TESTING.md)
