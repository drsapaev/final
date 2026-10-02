
# Ops / Deployment

## Quick Start (Docker Compose)

Run from the project root:

```bash
cp ops/.env.example ops/.env
# Fill every empty required value in ops/.env before starting the stack.
docker compose --env-file ops/.env -f ops/docker-compose.yml up --build
```

Services:

- Backend: `http://localhost:18000` (OpenAPI: `http://localhost:18000/docs`)
- Frontend (Vite dev): `http://localhost:5173`
- Postgres host port: `localhost:55432`

Minimum required environment:

- `DATABASE_URL`: PostgreSQL connection string using the compose service host, for example `postgresql+psycopg://clinic:<password>@postgres:5432/clinicdb`.
- `POSTGRES_PASSWORD`: unique database password.
- `SECRET_KEY` and `AUTH_SECRET`: unique generated secrets.
- `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_EMAIL`, `ADMIN_FULL_NAME`: bootstrap admin identity.
- `CORS_ALLOW_ALL=0` and `BACKEND_CORS_ORIGINS`: explicit frontend origins.
- `RUN_ALEMBIC_ON_START=1`: keep Alembic as the schema source of truth on startup.

Runtime notes:

- PostgreSQL + Alembic are the Docker runtime source of truth. SQLite is not a compose runtime target.
- The backend container listens on port `18000` internally and is published as host port `18000` by default.
- `postgres_data` stores PostgreSQL data. `backend_data` is only for backend runtime artifacts.
- The backend entrypoint rejects missing or SQLite `DATABASE_URL` values before starting Uvicorn.

Commands:

```bash
docker compose --env-file ops/.env -f ops/docker-compose.yml build
docker compose --env-file ops/.env -f ops/docker-compose.yml up -d --build
docker compose --env-file ops/.env -f ops/docker-compose.yml logs -f backend
docker compose --env-file ops/.env -f ops/docker-compose.yml logs -f frontend
```

Admin bootstrap is handled by backend startup scripts when `ENSURE_ADMIN=1`. Use a unique `ADMIN_PASSWORD`; do not rely on default admin credentials.

For production, run the backend behind a TLS reverse proxy and keep filled env files out of git.

## Staging

На Windows clinic-host staging работает в WSL2 Ubuntu 24.04. Запускайте его
из worktree проверяемого commit через общий launcher:

```powershell
Copy-Item ops/staging.env.sample ops/staging.env
# Заполните synthetic secrets, уникальный COMPOSE_PROJECT_NAME и свободные порты.
.\ops\scripts\wsl_staging.ps1 -Action Preflight -EnvFile ops/staging.env
.\ops\scripts\wsl_staging.ps1 -Action Start -EnvFile ops/staging.env
```

`Preflight` проверяет prerequisites до первого build, runtime readiness
помечает `NOT_RUN`. После запуска `Check` требует healthy stack. Ошибки
prerequisite фиксируйте и устраняйте до тестов.
Для долгих тестов и browser QA оборачивайте весь собственный validation-script
в `-Action Session -CommandArgs @(...)`: keeper работает до конца команды.
Обычный `Start` удерживает WSL только на время запуска.

Адреса текущего локального staging; для отдельного проекта выберите свободные:

- Frontend: `http://<STAGING_PUBLIC_HOST>:18080`
- Backend docs: `http://<STAGING_PUBLIC_HOST>:18001/docs`
- Postgres: `127.0.0.1:55432`

В sample env PostgreSQL host port — `15432`; задавайте фактический порт явно.
Launcher проверяет project, порты, mounts, health и доступ из Windows, вызывает
Docker внутри WSL через local socket и всегда выбирает `ops/compose.staging.yml`.
HEAD/mount и image IDs сами по себе не доказывают commit собранного frontend:
helper явно сообщает `served_revision_verified=false` и `worktree_dirty`.
Не выводите env или полный resolved Compose config: в них secrets.

Остановка только собственного проекта:

```powershell
.\ops\scripts\wsl_staging.ps1 -Action Stop -EnvFile ops/staging.env
```

Не используйте host-based staging как fallback на этом Windows host: legacy
helpers могут занять production `:18000`. Не останавливайте чужие проекты и
общую WSL distribution. Рецепты Session, PostgreSQL-required тестов, normal
Admin/2FA подготовки и повторяющихся ошибок:
[WSL_STAGING_SESSION.md](../docs/runbooks/WSL_STAGING_SESSION.md).
Полный gate перед production остаётся
[STAGING_VALIDATION.md](../docs/runbooks/STAGING_VALIDATION.md); успешный
launcher не заменяет его десять проверок.

## VPS / Production Rollout

Для Linux VPS используйте host-based rollout kit:

- [ops/vps/README.md](/C:/final/ops/vps/README.md)
- [VPS_HOST_ROLLOUT_RUNBOOK.md](/C:/final/docs/runbooks/VPS_HOST_ROLLOUT_RUNBOOK.md)

## Clinic Host / On-Prem Lifecycle

For a clinic-owned host or on-prem Linux install, use the same isolated-deployment model and follow:

- [docs/runbooks/CLINIC_HOST_INSTALL_RUNBOOK.md](/C:/final/docs/runbooks/CLINIC_HOST_INSTALL_RUNBOOK.md)
- [docs/runbooks/CLINIC_RELEASE_ARTIFACT_POLICY.md](/C:/final/docs/runbooks/CLINIC_RELEASE_ARTIFACT_POLICY.md)
- [docs/runbooks/CLINIC_PRE_RELEASE_CHECKLIST.md](/C:/final/docs/runbooks/CLINIC_PRE_RELEASE_CHECKLIST.md)
- [docs/runbooks/CLINIC_RELEASE_CANDIDATE_SUMMARY.md](/C:/final/docs/runbooks/CLINIC_RELEASE_CANDIDATE_SUMMARY.md)
- [docs/runbooks/CLINIC_PRE_RELEASE_EVIDENCE_PACK.md](/C:/final/docs/runbooks/CLINIC_PRE_RELEASE_EVIDENCE_PACK.md)
- [docs/runbooks/LOCAL_ONLY_EXTERNAL_SERVICES_POLICY.md](/C:/final/docs/runbooks/LOCAL_ONLY_EXTERNAL_SERVICES_POLICY.md)
- [docs/runbooks/LOCAL_ONLY_CLINIC_MASTER_CHECKLIST.md](/C:/final/docs/runbooks/LOCAL_ONLY_CLINIC_MASTER_CHECKLIST.md)
- [docs/runbooks/CONTROLLED_PILOT_GATE_RESULT.md](/C:/final/docs/runbooks/CONTROLLED_PILOT_GATE_RESULT.md)
- [docs/runbooks/CLINIC_UPDATE_REHEARSAL_RUNBOOK.md](/C:/final/docs/runbooks/CLINIC_UPDATE_REHEARSAL_RUNBOOK.md)
- [docs/runbooks/CLINIC_BACKUP_RESTORE_REHEARSAL_RUNBOOK.md](/C:/final/docs/runbooks/CLINIC_BACKUP_RESTORE_REHEARSAL_RUNBOOK.md)
- [docs/runbooks/CLINIC_STATE_SEPARATION_AUDIT.md](/C:/final/docs/runbooks/CLINIC_STATE_SEPARATION_AUDIT.md)
- [docs/runbooks/CLINIC_OPERATOR_CHECKLIST.md](/C:/final/docs/runbooks/CLINIC_OPERATOR_CHECKLIST.md)
- [docs/runbooks/CLINIC_EVIDENCE_PACK_TEMPLATE.md](/C:/final/docs/runbooks/CLINIC_EVIDENCE_PACK_TEMPLATE.md)
- [docs/runbooks/PILOT_LAUNCH_PACK.md](/C:/final/docs/runbooks/PILOT_LAUNCH_PACK.md)
- [docs/runbooks/PILOT_START_CHECKLIST.md](/C:/final/docs/runbooks/PILOT_START_CHECKLIST.md)
- [docs/runbooks/PILOT_INCIDENT_NOTE_TEMPLATE.md](/C:/final/docs/runbooks/PILOT_INCIDENT_NOTE_TEMPLATE.md)
- [docs/runbooks/PILOT_7_DAY_EVIDENCE_PACK.md](/C:/final/docs/runbooks/PILOT_7_DAY_EVIDENCE_PACK.md)
- [docs/runbooks/OPERATIONAL_PROOF_PACKET.md](/C:/final/docs/runbooks/OPERATIONAL_PROOF_PACKET.md)
- [docs/runbooks/CLINIC_PILOT_CONTOUR_TEMPLATE.md](/C:/final/docs/runbooks/CLINIC_PILOT_CONTOUR_TEMPLATE.md)
- [ops/vps/clinic_lifecycle.env.sample](/C:/final/ops/vps/clinic_lifecycle.env.sample)
- [ops/vps/scripts/health_check.py](/C:/final/ops/vps/scripts/health_check.py)
- [ops/vps/scripts/smoke_fresh_install.py](/C:/final/ops/vps/scripts/smoke_fresh_install.py)
- [ops/vps/scripts/smoke_post_update.py](/C:/final/ops/vps/scripts/smoke_post_update.py)
- [ops/vps/scripts/run_update_rehearsal.py](/C:/final/ops/vps/scripts/run_update_rehearsal.py)
- [ops/vps/scripts/run_backup_restore_rehearsal.py](/C:/final/ops/vps/scripts/run_backup_restore_rehearsal.py)
- [ops/vps/scripts/build_release_artifact.py](/C:/final/ops/vps/scripts/build_release_artifact.py)
- [ops/vps/scripts/import_release_artifact.py](/C:/final/ops/vps/scripts/import_release_artifact.py)
