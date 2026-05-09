[<- Previous Page](RECOVERY_PLAN.md) | [Back to README](../README.md) | [Next Page ->](API.md)

# Architecture

Canonical architecture source: `.ai-factory/ARCHITECTURE.md`

## Current Shape

```text
frontend React/Vite
  -> API clients
  -> backend FastAPI routers
  -> service layer
  -> repositories / SQLAlchemy models
  -> PostgreSQL via Alembic schema
```

## Backend Boundaries

- API routers live in `backend/app/api/v1/endpoints`.
- Business rules should live in `backend/app/services`.
- SQLAlchemy entities live in `backend/app/models`.
- Pydantic contracts live in `backend/app/schemas`.
- Migrations live in `backend/alembic/versions`.

## Frontend Boundaries

- Route SSOT lives in `frontend/src/routing/routeRegistry.js`.
- Access and route selectors live in `frontend/src/routing/routeSelectors.js` and `routeGuards.jsx`.
- Role pages live in `frontend/src/pages`.
- Shared UI and domain widgets live in `frontend/src/components`.
- API clients live in `frontend/src/api`.

## Architecture Risks

- `backend/app/api/v1/api.py` still mounts several legacy and duplicate surfaces.
- Some endpoint files mix compatibility behavior with canonical behavior.
- Some frontend role screens contain no-op or partially wired controls.
- Historical docs can conflict with executable source; prefer code, tests, migrations, and active runbooks.

## See Also

- [API](API.md)
- [Recovery Plan](RECOVERY_PLAN.md)
- [Security Checklist](SECURITY_CHECKLIST.md)
