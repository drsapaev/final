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
- Task 25 local proof: Alembic static checks passed (`heads`, `branches`, `history base:head`), but clean online upgrade could not be run. Staging `127.0.0.1:55432` was closed, Docker/Compose and `psql` were unavailable, and the reachable local PostgreSQL server on `5432` rejected creation of a throwaway database because the configured role lacks `CREATEDB`.

## Deployment Gates Before Promotion

- Run frontend build and targeted route tests.
- Run backend auth/RBAC/payment/upload/Telegram/AI targeted tests.
- Run `alembic upgrade head` against a disposable PostgreSQL database.
- The disposable target must be a dedicated database or container where creating/dropping a temporary verification database is explicitly allowed.
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
