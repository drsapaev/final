# Clinic Queue Manager — Документация

## Обзор
Модульная система для поликлиники (MVP):
- Очередь на день (выдача талонов, табло, WS)
- Визиты, услуги, платежи
- Лабораторные заявки (результаты)
- Онлайн-очередь / «открытие дня» (QR)
- Настройки (произвольные пары `category/key/value`)
- Аудит действий

## Технологии
- **Backend**: FastAPI, SQLAlchemy 2, Alembic, JWT (python-jose), ReportLab, qrcode, WebSocket (FastAPI)
- **Frontend**: React + Vite (без роутера; страницы-экраны)
- **Ops**: Dockerfile + docker-compose (dev), SQLite по умолчанию

---

## Запуск (Docker Compose, dev)
```bash
# из project-root/ops/
docker compose up --build

##Сервисы:

Backend: http://localhost:8000  (OpenAPI: http://localhost:8000/docs)

Frontend (Vite dev): http://localhost:5173


##Переменные окружения (минимум):

DATABASE_URL=sqlite:////data/app.db — БД в volume backend_data

AUTH_SECRET=change-me-in-prod — секрет для JWT

CORS_ALLOW_ALL=1 — разрешить CORS всем источникам (для локалки)


ESC/POS (опционально):

PRINTER_TYPE=none|network|usb, PRINTER_NET_HOST, PRINTER_NET_PORT, PRINTER_USB_VID, PRINTER_USB_PID


Volume:

backend_data:/data — хранит SQLite-файл и артефакты


##Команды:

docker compose build
docker compose up -d --build
docker compose logs -f backend
docker compose logs -f frontend

##Админ по умолчанию:

Скрипт backend/app/scripts/ensure_admin.py создаёт пользователя admin/admin (настраивается ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_EMAIL, ADMIN_FULL_NAME).



---

##Локальный запуск без Docker (dev)

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r <(pip freeze)  # либо установить зависимости из pyproject
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Frontend
cd ../frontend
npm i
npm run dev
# при необходимости VITE_API_BASE=http://localhost:8000/api/v1


---

API (база: /api/v1)

Части (основные):

GET /health — состояние (DB/app/env)

POST /auth/login (form) — токен; GET /auth/me

GET/POST/PUT/DELETE /patients — CRUD пациентов

GET/POST/PUT/DELETE /visits — визиты

GET/POST /lab — заявки и результаты

GET/POST /payments — платежи

GET /services — каталог услуг

GET/PUT/DELETE /settings — произвольные настройки

GET /queues/stats, POST /queues/next-ticket — дневная очередь

POST /appointments/open, GET /appointments/stats — онлайн-очередь

GET /appointments/qrcode — QR PNG

GET /print/ticket.pdf, GET /print/invoice.pdf — печать PDF

WS: ws://localhost:8000/ws/queue?department=Reg&date_str=YYYY-MM-DD


##Примеры:

# Health
curl http://localhost:8000/api/v1/health

# Логин (OAuth2 Password)
curl -X POST -d "username=admin&password=admin&grant_type=&scope=&client_id=&client_secret=" \
  http://localhost:8000/api/v1/auth/login

# Мои данные
curl -H "Authorization: Bearer <TOKEN>" http://localhost:8000/api/v1/auth/me


---

##Миграции

Конфигурация: backend/alembic.ini

Скрипты: backend/alembic/versions/

Применение:


cd backend
alembic upgrade head


---

##Печать

PDF билеты/счета — app/services/print.py

ESC/POS — app/services/escpos.py (переменные в settings)

Лого (опц.): CLINIC_LOGO_PATH=/path/logo.png, футер PDF_FOOTER_ENABLED=1



---

##Роли (минимально)

Admin, Registrar, Doctor, Lab, Cashier, User



---

##Известные ограничения (MVP)

Минимальные списки/фильтры на фронтенде

Без полноценного роутера/авторизации в UI (токен хранится локально)

В dev Docker конфиге фронт работает через Vite dev-сервер
