# PostgreSQL для Production

## Обзор

SQLite используется для разработки, но для production **обязателен PostgreSQL** из-за:
- Параллельных подключений (SQLite блокирует файл)
- Полного ACID compliance
- Масштабируемости до миллионов записей
- Надёжного резервного копирования
- Репликации и отказоустойчивости

## Быстрый старт

### 1. Установка PostgreSQL

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**Windows:**
1. Скачать установщик с https://www.postgresql.org/download/windows/
2. Запустить установщик, указать пароль для пользователя `postgres`
3. Запомнить порт (по умолчанию 5432)

**Docker:**
```bash
docker run -d \
  --name clinic-postgres \
  -e POSTGRES_USER=clinic_user \
  -e POSTGRES_PASSWORD=secure_password \
  -e POSTGRES_DB=clinic_db \
  -p 5432:5432 \
  -v clinic_data:/var/lib/postgresql/data \
  postgres:15
```

### 2. Создание базы данных

```bash
# Подключение как postgres
sudo -u postgres psql
```

```sql
-- Создание пользователя
CREATE USER clinic_user WITH PASSWORD 'ваш_надёжный_пароль';

-- Создание базы данных
CREATE DATABASE clinic_db 
    OWNER clinic_user
    ENCODING 'UTF8'
    LC_COLLATE 'ru_RU.UTF-8'
    LC_CTYPE 'ru_RU.UTF-8';

-- Права доступа
GRANT ALL PRIVILEGES ON DATABASE clinic_db TO clinic_user;

-- Для расширений (если нужны)
\c clinic_db
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

\q
```

### 3. Настройка .env

Создайте файл `.env` в директории `backend/`:

```env
# ===== PRODUCTION CONFIGURATION =====
ENV=production

# Database
DATABASE_URL=postgresql://clinic_user:ваш_надёжный_пароль@localhost:5432/clinic_db

# Security (ОБЯЗАТЕЛЬНО сгенерировать новый!)
SECRET_KEY=ваш_64_символьный_секретный_ключ

# CORS (укажите реальные домены)
CORS_DISABLE=0
CORS_ALLOW_ALL=0
CORS_ORIGINS=https://yourdomain.com,https://admin.yourdomain.com

# Optional: 2FA
DISABLE_2FA_REQUIREMENT=0
```

### 4. Генерация SECRET_KEY

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

⚠️ **ВАЖНО:** Никогда не храните SECRET_KEY в репозитории!

### 5. Миграции

```bash
cd backend
source .venv/bin/activate  # или .venv\Scripts\activate на Windows

# Применить все миграции
alembic upgrade head

# Проверить статус миграций
alembic current
```

## Конфигурация PostgreSQL

### postgresql.conf (рекомендации для production)

Файл обычно находится в `/etc/postgresql/15/main/postgresql.conf`

```ini
# Память
shared_buffers = 256MB          # 25% от RAM для БД
effective_cache_size = 768MB    # 75% от RAM
work_mem = 64MB                 # Для сортировок

# Подключения
max_connections = 100           # По числу воркеров
listen_addresses = 'localhost'  # Только локальные подключения

# Логирование
log_min_duration_statement = 1000  # Логировать запросы > 1сек
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d '

# Checkpoint
checkpoint_completion_target = 0.9
```

### pg_hba.conf (аутентификация)

Ограничьте подключения:

```
# Тип    База        Пользователь    Адрес           Метод
local   all         postgres                        peer
local   clinic_db   clinic_user                     scram-sha-256
host    clinic_db   clinic_user     127.0.0.1/32    scram-sha-256
host    clinic_db   clinic_user     ::1/128         scram-sha-256

# Запретить все остальные удалённые подключения
host    all         all             0.0.0.0/0       reject
```

После изменений:
```bash
sudo systemctl reload postgresql
```

## Резервное копирование

### Ручной backup

```bash
# Полный дамп
pg_dump -U clinic_user -h localhost clinic_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Сжатый дамп
pg_dump -U clinic_user -h localhost clinic_db | gzip > backup_$(date +%Y%m%d).sql.gz

# Только данные (без схемы)
pg_dump -U clinic_user -h localhost --data-only clinic_db > data_only.sql
```

### Автоматический backup (cron)

```bash
# Открыть crontab
crontab -e

# Добавить строку (backup каждый день в 2:00)
0 2 * * * pg_dump -U clinic_user clinic_db | gzip > /backups/clinic_$(date +\%Y\%m\%d).sql.gz

# Ротация (удаление бэкапов старше 30 дней)
0 3 * * * find /backups -name "clinic_*.sql.gz" -mtime +30 -delete
```

### Восстановление

```bash
# Из обычного дампа
psql -U clinic_user -d clinic_db < backup.sql

# Из сжатого дампа
gunzip -c backup.sql.gz | psql -U clinic_user -d clinic_db

# Полное пересоздание БД
dropdb -U postgres clinic_db
createdb -U postgres -O clinic_user clinic_db
psql -U clinic_user -d clinic_db < backup.sql
```

## Мониторинг

### Проверка подключений

```sql
-- Текущие подключения
SELECT count(*) as connections, 
       state, 
       usename 
FROM pg_stat_activity 
WHERE datname = 'clinic_db'
GROUP BY state, usename;

-- Активные запросы
SELECT pid, 
       now() - pg_stat_activity.query_start AS duration,
       query,
       state
FROM pg_stat_activity
WHERE datname = 'clinic_db'
  AND state != 'idle'
ORDER BY duration DESC;
```

### Размер БД

```sql
-- Размер базы данных
SELECT pg_size_pretty(pg_database_size('clinic_db'));

-- Размер таблиц
SELECT 
    relname as table_name,
    pg_size_pretty(pg_total_relation_size(relid)) as total_size
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 10;
```

### Медленные запросы

```sql
-- Включить статистику запросов
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Топ-10 медленных запросов
SELECT 
    round(total_exec_time::numeric, 2) as total_time_ms,
    calls,
    round(mean_exec_time::numeric, 2) as avg_time_ms,
    query
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;
```

## Проверка работоспособности

### Тест подключения из Python

```python
from sqlalchemy import create_engine

DATABASE_URL = "postgresql://clinic_user:password@localhost:5432/clinic_db"
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    result = conn.execute("SELECT version()")
    print(result.fetchone())
```

### Проверка через API

```bash
# Запуск сервера
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Проверка health
curl http://localhost:8000/api/v1/health
```

## Troubleshooting

### Ошибка подключения

```
psycopg2.OperationalError: could not connect to server
```

**Решение:**
1. Проверьте что PostgreSQL запущен: `systemctl status postgresql`
2. Проверьте порт: `netstat -tlnp | grep 5432`
3. Проверьте pg_hba.conf

### Ошибка прав доступа

```
psycopg2.OperationalError: FATAL: password authentication failed
```

**Решение:**
1. Проверьте пароль в `.env`
2. Пересоздайте пользователя:
   ```sql
   ALTER USER clinic_user WITH PASSWORD 'новый_пароль';
   ```

### Ошибка миграций

```
alembic.util.exc.CommandError: Target database is not up to date
```

**Решение:**
```bash
# Показать текущую версию
alembic current

# Показать историю
alembic history

# Принудительно установить версию (осторожно!)
alembic stamp head
```

## Чек-лист перед запуском в Production

- [ ] PostgreSQL установлен и запущен
- [ ] База данных и пользователь созданы
- [ ] `.env` настроен с правильными credentials
- [ ] `SECRET_KEY` сгенерирован и уникален
- [ ] `CORS_ORIGINS` содержит только разрешённые домены
- [ ] Миграции применены (`alembic upgrade head`)
- [ ] Backup настроен (cron или ручной)
- [ ] pg_hba.conf ограничивает доступ
- [ ] Логирование настроено
- [ ] Мониторинг подключений работает
