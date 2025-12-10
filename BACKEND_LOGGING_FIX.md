# Backend Logging Fix Report

## Проблема
После запуска FastAPI backend не выдавал логи после сообщения `INFO: Application startup complete.`

## Причина
1. **Отключенные access logs**: В `run_server_auto.py` был установлен `access_log=False`
2. **Высокий уровень логирования**: В `logging_config.py` uvicorn логгеры были настроены на `WARNING` вместо `INFO`
3. **Недостаточное логирование**: Не было явного middleware для отслеживания HTTP запросов
4. **Отладчик VSCode**: При запуске через отладчик используется другая конфигурация, не из `run_server_auto.py`

## Решение

### 1. Улучшенная конфигурация логирования в `app/main.py`
```python
# Явная настройка всех логгеров uvicorn
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

uvicorn_logger = logging.getLogger("uvicorn")
uvicorn_logger.setLevel(logging.INFO)
uvicorn_access = logging.getLogger("uvicorn.access")
uvicorn_access.setLevel(logging.INFO)
uvicorn_error = logging.getLogger("uvicorn.error")
uvicorn_error.setLevel(logging.INFO)
```

### 2. Добавлен Request Logging Middleware
```python
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        log.info(f"📥 {request.method} {request.url.path}")
        response = await call_next(request)
        process_time = time.time() - start_time
        log.info(f"📤 {request.method} {request.url.path} - {response.status_code} ({process_time:.3f}s)")
        return response
```

### 3. Улучшенные startup логи
```python
@app.on_event("startup")
async def _startup_tasks() -> None:
    log.info("=" * 80)
    log.info("🏥 CLINIC MANAGEMENT SYSTEM - STARTING UP")
    log.info("=" * 80)
    # ... validation and setup ...
    log.info("=" * 80)
    log.info("✅ SERVER READY - Waiting for requests...")
    log.info("=" * 80)
```

### 4. Обновлен `run_server_auto.py`
```python
access_log=True,  # Включаем логи запросов
```

### 5. Обновлен `app/core/logging_config.py`
```python
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)
logging.getLogger("fastapi").setLevel(logging.INFO)
```

## Результат
Теперь после запуска бэкенда вы будете видеть:
- ✅ Сообщения о запуске системы
- ✅ Регистрацию middleware и роутеров
- ✅ Список всех зарегистрированных маршрутов
- ✅ Каждый входящий HTTP запрос (📥)
- ✅ Каждый ответ с кодом статуса и временем обработки (📤)
- ✅ Все ошибки и предупреждения

## Как применить
**Перезапустите бэкенд** (остановите текущий процесс и запустите заново через отладчик или командную строку).

## Пример вывода
```
2025-12-08 08:00:00 - clinic.main - INFO - 🚀 Logging configured - all logs should be visible
2025-12-08 08:00:00 - clinic.main - INFO - Exception handlers registered
2025-12-08 08:00:00 - clinic.main - INFO - Chat WebSocket registered at /ws/chat
2025-12-08 08:00:00 - clinic.main - INFO - Audit middleware registered
2025-12-08 08:00:00 - clinic.main - INFO - Security middleware registered
2025-12-08 08:00:00 - clinic.main - INFO - Request logging middleware registered
2025-12-08 08:00:00 - clinic.main - INFO - ================================================================================
2025-12-08 08:00:00 - clinic.main - INFO - 🏥 CLINIC MANAGEMENT SYSTEM - STARTING UP
2025-12-08 08:00:00 - clinic.main - INFO - ================================================================================
2025-12-08 08:00:01 - clinic.main - INFO - ================================================================================
2025-12-08 08:00:01 - clinic.main - INFO - ✅ SERVER READY - Waiting for requests...
2025-12-08 08:00:01 - clinic.main - INFO - ================================================================================
INFO:     Application startup complete.
2025-12-08 08:00:05 - clinic.main - INFO - 📥 GET /api/v1/health
2025-12-08 08:00:05 - clinic.main - INFO - 📤 GET /api/v1/health - 200 (0.003s)
```

## Файлы изменены
- ✅ `backend/app/main.py` - основные изменения логирования + перемещен RequestLoggingMiddleware после CORS
- ✅ `backend/app/core/logging_config.py` - уровни логирования
- ✅ `backend/run_server_auto.py` - включены access logs
- ✅ `backend/start_server.py` - отключен reload, включены access logs
- ✅ `backend/start_server_verbose.py` - **НОВЫЙ** скрипт с максимальным логированием

## Устранение проблем

### Проблема: Логи не появляются даже после изменений

**Причина**: Сервер запущен с `reload=True`, что может вызывать проблемы с логированием при автоперезагрузке.

**Решение**:
1. **Остановите текущий процесс сервера** (Ctrl+C в терминале или Stop в отладчике)
2. **Запустите сервер заново** одним из способов:

   **Вариант A - Через новый verbose скрипт (РЕКОМЕНДУЕТСЯ)**:
   ```bash
   cd backend
   python start_server_verbose.py
   ```

   **Вариант B - Через обычный скрипт**:
   ```bash
   cd backend
   python start_server.py
   ```

   **Вариант C - Через uvicorn напрямую**:
   ```bash
   cd backend
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level info --access-log
   ```

### Проблема: Middleware не логирует запросы

**Причина**: RequestLoggingMiddleware был зарегистрирован ДО CORS middleware. В FastAPI middleware выполняются в обратном порядке регистрации.

**Решение**: Перемещен RequestLoggingMiddleware ПОСЛЕ CORS (уже исправлено в коде).

### Проблема: Видны только startup логи, но не запросы

**Проверьте**:
1. Действительно ли приходят запросы на сервер? Откройте `http://localhost:8000/` в браузере
2. Проверьте, что сервер запущен БЕЗ `reload=True`
3. Используйте `start_server_verbose.py` для максимального логирования

### Тестирование логирования

После запуска сервера откройте в браузере или через curl:
```bash
# Проверка health endpoint
curl http://localhost:8000/

# Проверка API
curl http://localhost:8000/api/v1/health
```

Вы должны увидеть в консоли:
```
2025-12-08 08:00:05 - clinic.main - INFO - 📥 GET /
2025-12-08 08:00:05 - clinic.main - INFO - 📤 GET / - 200 (0.003s)
```

## Новый скрипт: start_server_verbose.py

Создан новый скрипт запуска с **максимальным уровнем логирования**:
- ✅ Настраивает все логгеры ДО запуска приложения
- ✅ Использует детальную конфигурацию uvicorn
- ✅ Выводит все логи в stdout
- ✅ Отключен reload для стабильности
- ✅ Включены access logs

**Использование**:
```bash
cd backend
python start_server_verbose.py
```
