# Детальный анализ системы очередей - Инвентаризация зависимостей

**Дата анализа**: 2025-11-24
**Ветка**: feat/macos-ui-refactor
**Backup БД**: clinic.db.backup_refactor

---

## 1. ТЕКУЩЕЕ СОСТОЯНИЕ БАЗЫ ДАННЫХ

### ✅ КРИТИЧЕСКИЕ НАХОДКИ
1. **Поле `queue_time` УЖЕ СУЩЕСТВУЕТ** в таблице `queue_entries` (DATETIME)
2. **Поле `is_clinic_wide` УЖЕ СУЩЕСТВУЕТ** в таблице `queue_tokens` (BOOLEAN)
3. **Обе таблицы существуют**: `daily_queues` и `online_days`

### Схема таблицы `daily_queues`:
```sql
- id (INTEGER, PK)
- day (DATE, NOT NULL)
- specialist_id (INTEGER, NOT NULL) → FK к users.id ⚠️
- active (BOOLEAN, NOT NULL)
- opened_at (DATETIME)
- created_at (DATETIME)
- queue_tag (VARCHAR(32))
- online_start_time (VARCHAR(5), NOT NULL, default="07:00")
- online_end_time (VARCHAR(5), NOT NULL, default="09:00")
- max_online_entries (INTEGER, NOT NULL)
- cabinet_number (VARCHAR(20))
- cabinet_floor (INTEGER)
- cabinet_building (VARCHAR(50))
```

### Схема таблицы `online_days`:
```sql
- id (INTEGER, PK)
- department (VARCHAR(64), NOT NULL)
- date_str (VARCHAR(16), NOT NULL)
- start_number (INTEGER)
- is_open (BOOLEAN, NOT NULL, default=1)
UNIQUE (department, date_str)
```

### Схема таблицы `queue_entries`:
```sql
- id (INTEGER, PK)
- queue_id (INTEGER, NOT NULL, FK)
- number (INTEGER, NOT NULL)
- patient_id (INTEGER)
- patient_name (VARCHAR(200))
- phone (VARCHAR(20))
- telegram_id (BIGINT)
- source (VARCHAR(20), NOT NULL)
- status (VARCHAR(20), NOT NULL)
- created_at (DATETIME)
- called_at (DATETIME)
- visit_id (INTEGER)
- queue_time (DATETIME) ✅ УЖЕ ЕСТЬ
- ... (и другие поля)
```

### Схема таблицы `queue_tokens`:
```sql
- id (INTEGER, PK)
- token (VARCHAR(100), NOT NULL, UNIQUE)
- day (DATE, NOT NULL)
- specialist_id (INTEGER) → FK к doctors.id (nullable) ⚠️
- department (VARCHAR(50))
- is_clinic_wide (BOOLEAN, NOT NULL) ✅ УЖЕ ЕСТЬ
- generated_by_user_id (INTEGER)
- usage_count (INTEGER, NOT NULL)
- expires_at (DATETIME, NOT NULL)
- active (BOOLEAN, NOT NULL)
- created_at (DATETIME)
```

---

## 2. МОДЕЛИ ДАННЫХ

### Модель 1: `OnlineDay` (models/online.py)
**Статус**: УСТАРЕВШАЯ, используется только для appointments
**Использование**: 1 файл
- `services/online_queue.py` - единственный прямой импорт

**Особенности**:
- Простая модель для tracking открытых дней
- Работает через Settings таблицу для счетчиков
- Department-based (не specialist-based)
- Не имеет богатых возможностей DailyQueue

### Модель 2: `DailyQueue` + `OnlineQueueEntry` (models/online_queue.py)
**Статус**: ОСНОВНАЯ, используется везде
**Использование**: 36 файлов

**Критическая проблема**:
```python
# В models/online_queue.py строка 16:
specialist_id = Column(Integer, ForeignKey("users.id"), nullable=False)

# НО в QueueToken (строка 91):
specialist_id = Column(Integer, ForeignKey("doctors.id"), nullable=True)
```
**FK НЕСООТВЕТСТВИЕ**: DailyQueue → users.id, QueueToken → doctors.id

**Файлы импортирующие DailyQueue** (36 файлов):
- backend\app\api\v1\endpoints\registrar_integration.py
- backend\app\services\qr_queue_service.py
- backend\app\services\queue_service.py
- backend\app\api\v1\endpoints\registrar_wizard.py
- backend\app\services\print_service.py
- backend\app\services\analytics.py
- backend\app\api\v1\endpoints\doctor_integration.py
- backend\app\api\v1\endpoints\qr_queue.py
- backend\app\services\morning_assignment.py
- backend\app\api\v1\endpoints\visit_confirmation.py
- backend\app\api\v1\endpoints\queue.py
- backend\app\crud\online_queue.py
- backend\app\graphql\mutations.py
- backend\app\api\v1\endpoints\display_websocket.py
- backend\app\api\v1\endpoints\queue_limits.py
- backend\app\services\registrar_notification_service.py
- backend\app\services\reporting_service.py
- backend\app\graphql\resolvers.py
- backend\app\services\wait_time_analytics_service.py
- backend\app\api\v1\endpoints\registrar_notifications.py
- backend\app\services\user_data_transfer_service.py
- backend\app\api\v1\endpoints\queue_cabinet_management.py
- backend\app\services\display_websocket.py
- backend\app\api\v1\endpoints\queue_reorder.py
- backend\app\services\telegram_bot_enhanced.py
- backend\app\services\queue_auto_close.py
- backend\tests\integration\test_e2e_visit_flow.py
- backend\tests\integration\test_e2e_migration_flow.py
- backend\tests\integration\test_migration_management_api.py
- backend\tests\integration\test_visit_confirmation_api.py
- backend\tests\unit\test_migration_service.py
- backend\tests\conftest.py
- backend\app\services\migration_service.py
- backend\app\api\v1\endpoints\morning_assignment.py
- backend\test_full_integration_cycle.py
- backend\test_online_queue_system.py

---

## 3. СЕРВИСЫ

### Сервис 1: `services/online_queue.py`
**Статус**: Используется для appointments endpoint
**Импортируется в**: 7 файлов
- backend\app\api\v1\endpoints\appointments.py
- backend\test_broadcast_runtime.py
- backend\test_broadcast_direct.py
- backend\app\api\v1\endpoints\queues.py
- backend\app\api\v1\endpoints\board.py
- backend\app\api\v1\endpoints\online_queue.py
- backend\debug_ws.py

**Функции**:
- `get_or_create_day()` - работает с OnlineDay
- `load_stats()` - загружает статистику из Settings
- Использует Settings таблицу для счетчиков (key-value storage)
- `_broadcast()` - WebSocket broadcast

### Сервис 2: `services/queue_service.py`
**Статус**: Должен быть SSOT, но не единственный
**Импортируется в**: 14 файлов
- backend\app\api\v1\endpoints\registrar_integration.py
- backend\app\services\qr_queue_service.py
- backend\app\api\v1\endpoints\registrar_wizard.py
- backend\app\services\billing_service.py
- backend\app\api\v1\endpoints\payments.py
- backend\app\services\print_service.py
- backend\app\services\analytics.py
- backend\app\api\v1\endpoints\qr_queue.py
- backend\app\services\morning_assignment.py
- backend\app\api\v1\endpoints\online_queue_new.py
- backend\app\api\v1\endpoints\visit_confirmation.py
- backend\app\api\v1\endpoints\queue.py
- backend\app\crud\online_queue.py
- backend\app\api\v1\endpoints\queue_reorder.py

**Должен содержать**:
- Создание queue entries
- Управление queue numbers
- Duplicate checking
- Priority management

### Сервис 3: `services/qr_queue_service.py`
**Статус**: QR-специфичная логика
**Импортируется в**: Используется активно

**Функции**:
- Token generation/validation
- Session management
- Time window checks
- Делегирует к queue_service

### Сервис 4: `crud/online_queue.py` (765 строк!)
**Статус**: CRUD + БИЗНЕС-ЛОГИКА (нарушение разделения)
**Проблемы**:
- Содержит print statements (debug)
- Смешивает CRUD и бизнес-логику
- Дублирует функционал queue_service

---

## 4. API ENDPOINTS

### Активные роутеры на `/queue`:
1. `qr_queue.router` (api.py строка 161)
2. `queue_reorder.router` (api.py строка 241)
3. `queue_router` (api.py строка 250)

**КОНФЛИКТ**: Все три на одном префиксе!

### Отключенные endpoints:
1. `online_queue.router` - закомментирован (api.py строка 85-86, 186-187)
2. `online_queue_new.router` - закомментирован

### Appointments endpoint:
- Использует `services/online_queue.py`
- Работает с `OnlineDay` моделью
- Отдельная логика для очередей

---

## 5. КЛЮЧЕВЫЕ НАХОДКИ

### ✅ Что УЖЕ работает:
1. Поля `queue_time` и `is_clinic_wide` в БД
2. DailyQueue модель полнофункциональна
3. QR queue service частично реализован
4. Frontend QueueJoin.jsx существует

### ⚠️ Критические проблемы:
1. **FK несоответствие**: DailyQueue.specialist_id → users.id, но QueueToken.specialist_id → doctors.id
2. **Две модели для очередей**: OnlineDay vs DailyQueue
3. **Два сервиса для логики**: online_queue.py vs queue_service.py
4. **API routing conflicts**: 3 роутера на `/queue`
5. **Бизнес-логика размазана**: crud/online_queue.py содержит логику

### 🔍 Что нужно проверить:
1. Есть ли таблица `doctors` и связь с `users`?
2. Используются ли данные в `online_days` в production?
3. Какие endpoints реально используются frontend?

---

## 6. ПЛАН ДЕЙСТВИЙ (ОБНОВЛЕННЫЙ)

### ФАЗА 2.1: Исправить FK несоответствие
**Приоритет**: КРИТИЧЕСКИЙ
**Варианты**:
- A: Изменить DailyQueue.specialist_id → FK к doctors.id
- B: Добавить user_id в DailyQueue, specialist_id оставить

**Нужно проверить**: Структуру таблиц users и doctors

### ФАЗА 2.2: ~~Создать миграцию~~ НЕ НУЖНА!
**Статус**: ✅ ПРОПУСТИТЬ - поля уже существуют

### ФАЗА 2.3: Консолидировать модели
**Действие**:
- Сделать DailyQueue единственным SSOT
- Deprecated OnlineDay
- Migrate appointments endpoint

### ФАЗА 2.4: Консолидировать сервисы
**Действие**:
- queue_service.py = SSOT для бизнес-логики
- Убрать логику из crud/online_queue.py
- Удалить services/online_queue.py (после миграции)

---

## 7. РИСКИ

### Риск 1: Потеря данных в online_days
**Митигация**: Проверить использование, migrate данные если нужно

### Риск 2: Breaking appointments endpoint
**Митигация**: Тщательное тестирование, сохранить API совместимость

### Риск 3: FK migration может сломать существующие данные
**Митигация**: Проверить data integrity, dry-run migration

---

## СЛЕДУЮЩИЕ ШАГИ

1. ✅ Backup создан
2. ✅ Инвентаризация завершена
3. 🔄 Проверить структуру users/doctors tables
4. 🔄 Начать ФАЗУ 2.1 - Fix FK inconsistency
