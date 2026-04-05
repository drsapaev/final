
# Ops / Deployment

## Быстрый старт (Docker Compose)

```bash
# из project-root/ops/
docker compose up --build

Сервисы:

Backend: http://localhost:18000  (OpenAPI: http://localhost:18000/docs)

Frontend (Vite dev): http://localhost:5173


Переменные окружения (минимум):

DATABASE_URL=sqlite:////data/app.db — БД в volume backend_data

AUTH_SECRET=change-me-in-prod — секрет для JWT

CORS_ALLOW_ALL=1 — разрешить CORS всем источникам (для локалки)

ESC/POS (опционально): PRINTER_TYPE=none|network|usb, PRINTER_NET_HOST, PRINTER_NET_PORT, PRINTER_USB_VID, PRINTER_USB_PID


Volume:

backend_data:/data — хранит SQLite-файл и артефакты


Команды

Пересобрать: docker compose build

Перезапустить: docker compose up -d --build

Логи backend: docker compose logs -f backend

Логи frontend: docker compose logs -f frontend


Админ по умолчанию

Скрипт backend/app/scripts/ensure_admin.py создаёт пользователя admin/admin (настраивается переменными ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_EMAIL, ADMIN_FULL_NAME).

Прод

Для прод-сборки фронтенда используйте отдельный Nginx-контейнер с vite build и выдачей статики из dist/.

Backend рекомендуется запускать за реверс-прокси (Nginx) с TLS и переменными окружения, вынесенными в .env (не коммитить).

## Staging

Для staging используйте отдельный compose-стек:

```bash
# из project-root/
copy ops/staging.env.sample ops/staging.env
docker compose --env-file ops/staging.env -f ops/compose.staging.yml up -d --build
```

Основные адреса по умолчанию:

- Frontend: `http://<STAGING_PUBLIC_HOST>:18080`
- Backend docs: `http://<STAGING_PUBLIC_HOST>:18000/docs`
- Postgres: `127.0.0.1:15432`

После старта стека прогоните EMR cutover уже на staging:

```bash
docker compose --env-file ops/staging.env -f ops/compose.staging.yml exec backend python scripts/run_emr_cutover.py --pretty
```

Если Docker Desktop ведёт себя нестабильно, используйте host-based staging:

```bash
powershell -ExecutionPolicy Bypass -File ops/scripts/start_staging_host.ps1
powershell -ExecutionPolicy Bypass -File ops/scripts/run_staging_cutover_host.ps1
```

Остановить host-based staging:

```bash
powershell -ExecutionPolicy Bypass -File ops/scripts/stop_staging_host.ps1
```

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
