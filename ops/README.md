
# Ops / Deployment

## Быстрый старт (Docker Compose)

```bash
# из project-root/ops/
docker compose up --build

Сервисы:

Backend: http://localhost:8000  (OpenAPI: http://localhost:8000/docs)

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