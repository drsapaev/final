[<- Previous Page](TESTING.md) | [Back to README](../README.md)

# Deployment

## Runtime Defaults

| Service | Default |
|---|---|
| Backend | `http://localhost:18000` |
| Frontend | `http://localhost:5173` |
| Staging PostgreSQL host port | `55432` |

## Current Verified Deployment Facts

- `ops/compose.staging.yml` now defaults staging PostgreSQL host port to `55432`.
- `ops/README.md` now documents `127.0.0.1:55432` for staging PostgreSQL.
- Alembic revision chain is linear with head `0022_service_audit_log`.
- Local clean online upgrade could not be run because Docker/Compose and `psql` were unavailable, `127.0.0.1:55432` was closed, and `127.0.0.1:5432` may be a live/dev database.

## Deployment Gates Before Promotion

- Run frontend build and targeted route tests.
- Run backend auth/RBAC/payment/upload/Telegram/AI targeted tests.
- Run `alembic upgrade head` against a disposable PostgreSQL database.
- Verify backup and rollback on the same deployment contour.
- Verify environment variables come from env/secret store, not tracked files.
- Keep `VITE_ENABLE_INTERNAL_DEMO` unset in production-like environments.
- Keep fallback auth disabled unless an explicit break-glass runbook authorizes it.

## Environment Notes

- PostgreSQL + Alembic are the database source of truth.
- Do not reintroduce SQLite-first defaults.
- External services such as Telegram, SMS, FCM, cloud AI, and public payment webhooks must be optional until explicitly configured.

## See Also

- [Testing](TESTING.md)
- [Security Checklist](SECURITY_CHECKLIST.md)
- [Recovery Plan](RECOVERY_PLAN.md)
