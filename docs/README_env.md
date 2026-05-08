# Переменные окружения (Backend/Frontend)

## Backend (`backend/.env`)
- `ENV` — окружение: `dev|stage|prod`.
- `APP_NAME` / `APP_VERSION` — метаданные приложения.
- `API_V1_STR` — префикс API (по умолчанию `/api/v1`).
- `CORS_ALLOW_ALL` - local diagnostics only. Keep it `0` in `stage|prod`; configure explicit origins with `CORS_ORIGINS`.
- `CORS_ORIGINS` — CSV список источников (например, `http://localhost:5173,http://localhost:4173`).
- `DATABASE_URL` — строка подключения к PostgreSQL (локальный пример: `postgresql+psycopg://clinic:<db_password>@localhost:55432/clinicdb`).
- `AUTH_SECRET` / `ACCESS_TOKEN_EXPIRE_MINUTES` / `AUTH_ALGORITHM` — параметры JWT.
- `CLINIC_LOGO_PATH` / `PDF_FOOTER_ENABLED` — печать и PDF.
- `PRINTER_*` — параметры ESC/POS (тип/сеть/USB).
- `REQUIRE_LICENSE` — включить лицензионный режим.
- `LICENSE_ALLOW_HEALTH` — разрешить `/api/v1/health` до активации.

## Frontend (`frontend/.env`)
- `VITE_APP_NAME` — название в UI.
- `VITE_API_BASE` — базовый адрес API (например, `http://localhost:18000/api/v1`).

## Быстрый старт (локально)
```bash
# Backend
cp backend/.env.example backend/.env
# при необходимости отредактируйте значения
# uvicorn app.main:app --reload --port 18000  (из каталога backend)

# Frontend
cp frontend/.env.example frontend/.env
# npm install && npm run dev  (из каталога frontend)
