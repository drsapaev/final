[Back to README](../README.md) | [Next Page ->](RECOVERY_PLAN.md)

# Project Audit

Audit date: 2026-05-09

Status source: `.ai-factory/logs/RECOVERY_IMPLEMENTATION_STATUS.md`

## Stack

- Backend: Python 3.11, FastAPI, SQLAlchemy, Pydantic v2.
- Database: PostgreSQL with Alembic migrations as source of truth.
- Frontend: React 18, Vite, React Router, JavaScript/JSX.
- Runtime defaults: backend `18000`, frontend `5173`, staging PostgreSQL `55432`.
- Product: clinic EMR and operations platform for admin, registrar, doctor, cashier, lab, queue, billing, and rollout workflows.

## Current Diagnosis

| Check | Current evidence |
|---|---|
| Frontend build | Passing in recent targeted runs; Vite still warns about large chunks and mixed dynamic/static `errorHandler.js` imports. |
| Backend syntax for changed endpoints | Passing through targeted `py_compile` runs. |
| Full backend test suite | Not proven in this recovery session. |
| Alembic chain | 22 linear revisions verified; online clean upgrade remains blocked locally without disposable PostgreSQL. |
| Auth P0 | Canonical login no longer uses minimal-login bypass; fallback auth is disabled by default. |
| Payment P0 | Singular webhook no longer returns successful HTTP status for processing failures. |
| Upload P0 | Simple upload is disabled unless explicitly enabled and now has basic file gates. |
| Telegram P1 | Webhook surfaces fail closed when secret is missing and avoid full payload logging in patched paths. |
| AI P1 | Legacy AI now has a coarse AI RBAC gate; EMR AI exposes draft-only metadata; visible assistant shows human-confirmation warning. |
| Production readiness | Not proven. Treat as recovery-in-progress. |

## Priority Findings

### P0 Fixed Or Mitigated In This Recovery Slice

- 2FA bypass risk through canonical frontend login path.
- OAuth2 token URL pointing at fallback auth.
- Tracked plaintext auth fixture files.
- Payment webhook silent-loss behavior on processing failures.
- Production-mounted simple file upload without sufficient gates.

### P1 Remaining

- Clean Alembic upgrade must be run against an explicitly disposable PostgreSQL target.
- Legacy `/api/v1/ai/*` still needs migration toward the canonical AI gateway contract.
- AI mock provider is still initialized by default; decide whether this is allowed outside explicit demo/test mode.
- Payment callback duplication still needs provider-canonical URL ownership and reconciliation proof.
- Patient own-data RBAC linkage remains incomplete in existing tests.
- Telegram notification retry/outbox and PHI response minimization still need follow-up.

### P2 Remaining

- `pytest.mark.asyncio` is used while `backend/pytest.ini` has `--strict-markers` without an `asyncio` marker entry.
- Large frontend chunks and dynamic/static import warnings remain.
- Several historical docs and reports can still mislead agents if treated as proof.

### P3 Remaining

- Landing, microcopy, and visual polish should wait until critical clinical flows and security gates are mechanically green.

## See Also

- [Recovery Plan](RECOVERY_PLAN.md)
- [Security Checklist](SECURITY_CHECKLIST.md)
- [Testing](TESTING.md)
