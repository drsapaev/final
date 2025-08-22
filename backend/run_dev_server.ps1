# Перейти в папку проекта
cd C:\final\backend

# Активировать виртуальное окружение
.\.venv\Scripts\Activate.ps1

# Установить переменные окружения
$env:WS_DEV_ALLOW = "1"
$env:CORS_DISABLE = "1"
$env:REQUIRE_LICENSE = "0"

# Запустить сервер
uvicorn app.main:app --reload --port 8000 --reload-exclude ".venv"
