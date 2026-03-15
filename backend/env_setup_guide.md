# Руководство по настройке переменных окружения

Reviewed For Drift: 2026-03-14
Status: dev-first env setup guide with current caveats

## Как использовать этот файл

Это не полный production runbook и не замена шаблона env.

Используйте этот файл как короткий dev/local entry guide, а канонические
опорные точки берите из:

- `C:/final/backend/.env.example`
- `C:/final/backend/SETUP_PRODUCTION.md`
- `C:/final/ops/.env.example`

Current verification baseline:

- `pytest tests/test_openapi_contract.py -q` -> `14 passed`
- `pytest -q` -> `850 passed, 3 skipped`

## Что настроить сейчас

### 1. Сначала скопировать шаблон

Вместо создания пустого `.env` вручную используйте живой шаблон:

```powershell
cd C:\final\backend
Copy-Item .env.example .env
```

Это безопаснее, потому что текущий `.env.example` уже содержит проверенные
базовые ключи и комментарии.

### 2. Обязательный минимум для local/dev

Проверьте и при необходимости отредактируйте:

```env
ENV=dev
DATABASE_URL=sqlite:///./clinic.db
SECRET_KEY=change_me_please_64chars_minimum________________________________
CORS_ALLOW_ALL=0
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
TIMEZONE=Asia/Tashkent
```

Примечания:

- backend сейчас принимает и `CORS_ORIGINS`, и `BACKEND_CORS_ORIGINS`
- `SECRET_KEY` должен быть не короче `32` символов
- для local/dev по умолчанию используется SQLite

### 3. Если нужен новый `SECRET_KEY`

```powershell
cd C:\final\backend
python generate_secret_key.py
```

После этого вставьте значение в `.env`.

## Что уже есть в шаблоне `.env.example`

Текущий `backend/.env.example` уже покрывает:

- базовые app values
- SQLite dev database
- JWT/`SECRET_KEY`
- CORS
- timezone/queue basics
- printing basics
- tenant-scope flags
- licensing basics

То есть для простого local/dev старта обычно достаточно:

1. скопировать `.env.example`
2. заменить `SECRET_KEY`
3. при необходимости поправить CORS и `DATABASE_URL`

## Что настраивается позже или по необходимости

Эти зоны в проекте есть, но они не обязательны для первого локального старта:

- FCM / push notifications
- Telegram
- платежные интеграции
- принтеры
- PostgreSQL/ops deployment env
- AI provider keys

Важная оговорка:

- старые ссылки на `docs/FCM_SETUP_GUIDE.md` удалены из этого guide, потому что
  такого repo-local документа сейчас нет

## Быстрый local/dev старт

```powershell
cd C:\final\backend
Copy-Item .env.example .env
python generate_secret_key.py
```

Дальше:

1. вставьте новый `SECRET_KEY` в `.env`
2. при необходимости проверьте `CORS_ORIGINS`
3. запустите backend:

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Если нужен production/ops env

Для production-style настройки смотрите не этот файл, а:

- `C:/final/backend/SETUP_PRODUCTION.md`
- `C:/final/backend/PRODUCTION_SETUP_SUMMARY.md`
- `C:/final/ops/README.md`
- `C:/final/ops/.env.example`

Там уже зафиксированы текущие caveats:

- `backend/.env.production` не коммитится
- compose всё ещё содержит legacy `AUTH_SECRET`
- active backend config валидирует `SECRET_KEY`
- compose defaults требуют review перед non-local запуском

## Приоритеты

### Критично сразу

1. `SECRET_KEY`
2. `DATABASE_URL`
3. CORS values

### Обычно нужно вскоре после старта

4. `TIMEZONE`
5. queue-related values
6. printer/PDF settings, если используется печать

### Опционально

7. FCM
8. Telegram
9. payment provider keys
10. AI provider keys

## Безопасность

- никогда не коммитьте `.env`
- не оставляйте слабый `SECRET_KEY`
- для production используйте отдельный env path и отдельные значения
- не считайте local/dev defaults production-safe по умолчанию
