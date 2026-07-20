## План: миграция clinic_dev (0030→0044) + cleanup + переключение на canonical dev workflow

### Контекст

Ты работаешь в VS Code (Launch `Backend: FastAPI (run_server.py)`) + AI-агенты. Данные нужны только для тестирования. После анализа:

- **VS Code `.env`** указывает на `localhost:5432/clinicdb` (native PG, пароль `clinicpwd`)
- **clinic_dev (:5432)** содержит твои тестовые данные: 65 services, 8 users, 15 patients, 5 departments, 4 doctors, 45 visits (alembic `0030`)
- **clinicdb (:5432)** — 1 patient Telegram/QRTEST, тестовая (ты подтвердил — удалить)
- **docker staging (:55432)** — нестабилен (restart-loop WSL из-за 7.7GB RAM на Windows)
- **Все 14 миграций 0031→0044 безопасны** для существующих данных (ноль DROP, ноль сужающих ALTER, все NOT NULL имеют server_default)

### Решение: clinic_dev canonical + native dev workflow

Это устраняет сразу 5 проблем из списка 🟠:
- **#4 Restart-loop** — нет Docker → нет restart-loop
- **#5 portproxy на временный IP** — не нужен (native localhost)
- **#6 Два Postgres** — остаётся один (native :5432)
- **#7 .env пароль** — починим (создадим роль `clinic`)
- Освобождается ~1.5 GB RAM (Docker VM + 5 контейнеров)

### Шаги выполнения

#### Шаг 1: Backup clinic_dev (safety net)
```bash
# pg_dump clinic_dev → C:\Users\DrSapaev\clinic_dev_backup_2026-07-19.sql
pg_dump -h localhost -U postgres -d clinic_dev > clinic_dev_backup.sql
```
Если что-то пойдёт не так — restore возможен.

#### Шаг 2: Upgrade alembic 0030 → 0044 на clinic_dev
```bash
cd backend
DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/clinic_dev" \
  .venv/Scripts/python.exe -m alembic upgrade head
# Verify: alembic current → должно показать 0044_audit_logs
```
Все 65 services, 8 users, 15 patients **остаются нетронутыми**. Новые колонки (`patients.emergency_contact`, `users.push_notifications_enabled` и т.д.) получат NULL или server_default.

#### Шаг 3: Удалить clinicdb (:5432) — тестовую
```sql
-- Connect as postgres, drop clinicdb
DROP DATABASE clinicdb;
-- Recreate empty clinicdb (для .env, который указывает на clinicdb)
CREATE DATABASE clinicdb OWNER clinic;
```
**Почему recreate пустой**: `.env` указывает на `clinicdb`, многие скрипты ожидают это имя. Создадим пустую clinicdb, в которую при необходимости можно заливать fresh demo seed через `dev_seed.py`.

#### Шаг 4: Применить миграции к пустой clinicdb + залить demo seed
```bash
DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/clinicdb" \
  .venv/Scripts/python.exe -m alembic upgrade head
# → 0044_audit_logs

# Demo seed для тестирования AI/fresh UI:
DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/clinicdb" \
  .venv/Scripts/python.exe -m app.scripts.dev_seed --allow-remote-dev-db --confirm-dev-seed
```

#### Шаг 5: Починить роль `clinic` в native PG (чтобы .env пароль работал)
```sql
-- Сейчас работает только postgres:postgres (peer auth).
-- Создадим роль clinic с паролем из .env (clinicpwd):
CREATE ROLE clinic WITH LOGIN PASSWORD 'clinicpwd';
GRANT ALL PRIVILEGES ON DATABASE clinicdb TO clinic;
GRANT ALL PRIVILEGES ON DATABASE clinic_dev TO clinic;
-- После создания пустой clinicdb и миграций:
GRANT ALL ON ALL TABLES IN SCHEMA public TO clinic;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO clinic;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO clinic;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO clinic;
```
Это решает проблему #7 — `.env DATABASE_URL` с `clinic:clinicpwd` начнёт работать.

#### Шаг 6: Остановить docker staging (освободить RAM)
```bash
wsl -d Ubuntu-24.04 -- bash -c "
  cd /mnt/c/final/ops
  sudo docker compose down
"
# Опционально: docker images cleanup
wsl -d Ubuntu-24.04 -- bash -c "sudo docker system prune -a -f"
wsl --shutdown  # освободить vmmemWSL (1.3 GB)
```

#### Шаг 7: Очистить netsh portproxy (больше не нужны)
```powershell
# Требует admin (UAC prompt):
netsh interface portproxy delete v4tov4 listenport=55432 listenaddress=127.0.0.1
netsh interface portproxy delete v4tov4 listenport=6379 listenaddress=127.0.0.1
netsh interface portproxy delete v4tov4 listenport=18000 listenaddress=127.0.0.1
netsh interface portproxy delete v4tov4 listenport=5173 listenaddress=127.0.0.1
```

#### Шаг 8: Финальная валидация
```bash
cd backend
# a) .env DATABASE_URL работает:
.venv/Scripts/python.exe -c "
import psycopg
from app.core.config import settings
c = psycopg.connect(settings.DATABASE_URL)
cur = c.cursor()
cur.execute('SELECT count(*) FROM services')
print(f'services: {cur.fetchone()[0]}')
"
# b) Backend стартует (compile check):
.venv/Scripts/python.exe -c "from app.main import app; print(f'Routes: {len(app.routes)}')"
# c) Pytest subset:
.venv/Scripts/python.exe -m pytest tests/unit/test_pii_masker.py -v
```

### Что НЕ делаем

- ❌ Не переносим services/users из clinic_dev в docker staging — docker staging упраздняется
- ❌ Не трогаем данные clinic_dev (только schema upgrade)
- ❌ Не удаляем WSL/Docker — оставляем установленным на будущее (когда будет больше RAM)
- ❌ Не коммитим `.env` (там реальные API-ключи)

### Риски и mitigations

| Риск | Mitigation |
|------|-----------|
| alembic upgrade ломает данные | Невозможно по анализу: ноль DROP, ноль сужающих ALTER. + Backup в шаге 1 |
| Потеря clinic_dev | Backup в шаге 1 (pg_dump) |
| `.env` пароль всё ещё не работает | Шаг 5 явно создаёт роль clinic |
| Хочешь вернуть Docker staging позже | WSL+Docker остаются установленными, compose файл не трогаем, можно поднять через `docker compose up -d` |

### Результат

После выполнения:
- ✅ 1 canonical dev workflow: VS Code → native Python (.venv) → native PG :5432
- ✅ clinic_dev на актуальной схеме 0044, твои 65 services / 8 users на месте
- ✅ clinicdb (пустая, demo-seeded) для fresh UI/AI тестов
- ✅ Роль `clinic` работает, `.env DATABASE_URL` валиден
- ✅ Docker staging остановлен, ~1.5 GB RAM свободно
- ✅ portproxy удалены (больше не нужны)
- ✅ 5 проблем 🟠 из 10 решены

### Что НЕ покрывает этот план (остаётся в backlog)

- 🟡 Backend minor bugs (F-017 retention, LabNotification) — нужны отдельные issue/PR
- 🟡 `master.key` chmod warning на Windows — косметика
- 🟡 `SECRET_KEY` static dev default — это OK для dev, при production deploy нужно менять
- 🔴 Реальные API-ключи в `.env` (GEMINI, DEEPSEEK) — рекомендую переместить в secrets.json (через setup_secrets encrypt) отдельно