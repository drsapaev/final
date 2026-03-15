# Operator Startup Commands

Updated: 2026-03-14
Status: canonical explicit startup command map

## How to read this file

All commands below assume you start from the repository root:

```bash
cd final
```

Use this file when you want the shortest explicit operator flow after the
startup hardening and `ensure_admin` contract hardening slices.

## Direct Backend Path

### Prepare schema

```bash
cd backend
alembic upgrade head
alembic current
```

### Optional admin bootstrap

Create-only default:

```bash
cd backend
python app/scripts/ensure_admin.py
```

Explicit existing-user mutation:

```bash
cd backend
ADMIN_ALLOW_UPDATE=1 python app/scripts/ensure_admin.py
```

Explicit existing-user password reset:

```bash
cd backend
ADMIN_ALLOW_UPDATE=1 ADMIN_RESET_PASSWORD=1 python app/scripts/ensure_admin.py
```

### Start app

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Compose Path

### Prepare schema

```bash
docker compose -f ops/docker-compose.yml run --rm backend alembic upgrade head
```

### Optional admin bootstrap

Create-only default:

```bash
docker compose -f ops/docker-compose.yml run --rm backend python app/scripts/ensure_admin.py
```

Explicit existing-user mutation:

```bash
docker compose -f ops/docker-compose.yml run --rm -e ADMIN_ALLOW_UPDATE=1 backend python app/scripts/ensure_admin.py
```

Explicit existing-user password reset:

```bash
docker compose -f ops/docker-compose.yml run --rm -e ADMIN_ALLOW_UPDATE=1 -e ADMIN_RESET_PASSWORD=1 backend python app/scripts/ensure_admin.py
```

### Start stack

```bash
docker compose -f ops/docker-compose.yml up --build -d
```

## Reader Rules

- schema prep is explicit
- admin bootstrap is explicit
- existing-user mutation is explicit
- if `backend/.env.production` is missing, compose runtime still needs operator
  setup before the stack can be treated as ready
