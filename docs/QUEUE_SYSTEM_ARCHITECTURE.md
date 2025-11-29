# Архитектура системы очередей - SSOT Guide

**Дата**: 2025-11-24
**Статус**: ✅ Active
**Версия**: 2.0

---

## 📌 Single Source of Truth (SSOT)

### ✅ Официальные модели (ИСПОЛЬЗУЙТЕ ЭТИ)

**Расположение**: `backend/app/models/online_queue.py`

1. **DailyQueue** - Дневные очереди по специалистам
   - FK к `doctors.id` (specialist-based)
   - Информация о кабинете
   - Временные ограничения для онлайн-записи
   - Relationship к queue entries

2. **OnlineQueueEntry** - Записи в очереди
   - FK к `daily_queues.id`
   - Полная информация о пациенте
   - Поле `queue_time` для приоритизации
   - Поле `source` для tracking источника
   - Связь с визитами и услугами

3. **QueueToken** - QR токены
   - FK к `doctors.id` (nullable для clinic-wide QR)
   - Поле `is_clinic_wide` для общих QR
   - Expiration tracking
   - Usage counting

### ❌ Устаревшие модели (НЕ ИСПОЛЬЗУЙТЕ)

**Расположение**: `backend/app/models/online.py`

1. **OnlineDay** - DEPRECATED
   - Department-based (строковый идентификатор)
   - Использует Settings таблицу для счетчиков
   - Только для appointments endpoint (legacy)
   - **Не добавляйте новые функции!**

---

## 🏗️ Архитектура

### Specialist-based vs Department-based

#### ✅ Specialist-based (SSOT - DailyQueue)
```
User (врач) → Doctor (профиль) → DailyQueue (очередь) → OnlineQueueEntry (записи)
     └─ full_name           └─ specialty        └─ opened_at          └─ queue_time
        username               cabinet              queue_tag             source
```

**Преимущества**:
- Четкая привязка к конкретному врачу
- Поддержка нескольких врачей одной специальности
- Детальная информация о кабинете
- Полный контроль временных окон
- Связь с визитами и услугами

#### ❌ Department-based (DEPRECATED - OnlineDay)
```
Department (строка) → OnlineDay → Settings (key-value counters)
     "cardiology"      is_open      "cardiology::2025-01-15::last_ticket" = "15"
```

**Недостатки**:
- Нет привязки к конкретному врачу
- Счетчики разбросаны по Settings таблице
- Нет информации о кабинете
- Упрощенная логика
- Только для простых случаев

---

## 🔄 Сервисы (Service Layer)

### ✅ Официальный SSOT сервис

**`backend/app/services/queue_service.py`**

**Функции**:
- `get_queue_service()` - Получить singleton instance
- `assign_queue_token()` - Создать QR токен
- `join_queue_with_token()` - Присоединиться к очереди
- `create_queue_entry()` - Создать запись в очереди
- `get_next_queue_number()` - Получить следующий номер
- `get_queue_statistics()` - Получить статистику

**Используйте для**:
- Всех операций с очередью
- Создания queue entries
- Генерации QR кодов
- Получения статистики

### ❌ Устаревший сервис

**`backend/app/services/online_queue.py`** - DEPRECATED

**Функции**:
- `get_or_create_day()` - Работает с OnlineDay
- `issue_next_ticket()` - Простая выдача талонов
- `load_stats()` - Статистика из Settings

**Используется только для**:
- Appointments endpoint (backward compatibility)
- НЕ использовать для новых функций!

---

## 📊 Примеры использования

### ✅ Правильно (используем DailyQueue)

```python
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.services.queue_service import get_queue_service

# Получить очередь по специалисту
queue = db.query(DailyQueue).filter(
    DailyQueue.specialist_id == doctor.id,
    DailyQueue.day == target_date
).first()

# Создать запись через сервис
queue_service = get_queue_service()
entry = queue_service.create_queue_entry(
    db=db,
    queue_id=queue.id,
    patient_name="Иванов Иван",
    phone="+998901234567",
    source="online",
    queue_time=datetime.now(timezone)  # Важно: сохраняет приоритет
)

# Получить имя врача
doctor_name = queue.specialist.user.full_name if (queue.specialist and queue.specialist.user) else "Врач"
```

### ❌ Неправильно (используем OnlineDay)

```python
from app.models.online import OnlineDay  # ❌ DEPRECATED!
from app.services.online_queue import issue_next_ticket  # ❌ DEPRECATED!

# НЕ ДЕЛАЙТЕ ТАК для новых функций!
ticket, stats = issue_next_ticket(
    db=db,
    department="cardiology",  # ❌ Строковый department
    date_str="2025-01-15"
)
```

---

## 🚀 План миграции

### Этап 1: SSOT Установлен (✅ ЗАВЕРШЕНО)

- [x] DailyQueue помечен как SSOT
- [x] OnlineDay помечен как DEPRECATED
- [x] Добавлены предупреждения в код
- [x] Создана документация

### Этап 2: Новые функции (🔄 В ПРОЦЕССЕ)

- [ ] Все новые queue endpoints используют DailyQueue
- [ ] QR queue система полностью на DailyQueue
- [ ] Frontend использует новые API

### Этап 3: Миграция appointments (📋 ЗАПЛАНИРОВАНО)

- [ ] Создать адаптер OnlineDay → DailyQueue
- [ ] Обновить appointments endpoint
- [ ] Мигрировать данные из online_days в daily_queues
- [ ] Тестирование backward compatibility

### Этап 4: Удаление legacy (🔮 БУДУЩЕЕ)

- [ ] Удалить OnlineDay model
- [ ] Удалить online_queue.py service
- [ ] Удалить таблицу online_days
- [ ] Очистить Settings от queue counters

---

## 📋 Чек-лист для разработчиков

Перед добавлением функционала очереди, проверьте:

- [ ] ✅ Используете `DailyQueue` из `models/online_queue.py`
- [ ] ✅ Используете `queue_service.py` для операций
- [ ] ✅ Обращаетесь к врачу через `queue.specialist.user.full_name`
- [ ] ✅ Используете `queue_time` для приоритизации
- [ ] ✅ Устанавливаете `source` корректно (`'online'`, `'desk'`, `'morning_assignment'`)
- [ ] ❌ НЕ используете `OnlineDay` модель
- [ ] ❌ НЕ используете `online_queue.py` сервис
- [ ] ❌ НЕ используете Settings таблицу для счетчиков очереди

---

## 🔍 Различия в деталях

### Queue Number Generation

**DailyQueue подход**:
```python
# Получаем максимальный номер из queue_entries
max_number = db.query(func.max(OnlineQueueEntry.number)).filter(
    OnlineQueueEntry.queue_id == queue_id
).scalar() or 0

next_number = max_number + 1
```

**OnlineDay подход** (DEPRECATED):
```python
# Используем Settings таблицу
last_ticket = _get_int(db, f"{department}::{date}::last_ticket", 0)
next_number = last_ticket + 1
_set_int(db, f"{department}::{date}::last_ticket", next_number)
```

### Priority Management

**DailyQueue подход**:
```python
# Используем queue_time для сортировки
entries = db.query(OnlineQueueEntry).filter(
    OnlineQueueEntry.queue_id == queue_id
).order_by(OnlineQueueEntry.queue_time).all()  # ✅ Сохраняет приоритет
```

**OnlineDay подход** (DEPRECATED):
```python
# Нет queue_time - только номер талона
# Приоритет определяется только номером
```

---

## 🛠️ Troubleshooting

### Проблема: AttributeError: 'Doctor' object has no attribute 'full_name'

**Причина**: Пытаетесь обратиться к `queue.specialist.full_name`, но `specialist` это `Doctor` объект

**Решение**:
```python
# ❌ Неправильно
name = queue.specialist.full_name

# ✅ Правильно
name = queue.specialist.user.full_name if (queue.specialist and queue.specialist.user) else "Врач"
```

### Проблема: Queue entries не сортируются по времени регистрации

**Причина**: Не используется `queue_time` поле

**Решение**:
```python
# ✅ Правильно
entries = db.query(OnlineQueueEntry).filter(
    OnlineQueueEntry.queue_id == queue_id
).order_by(OnlineQueueEntry.queue_time).all()  # Сортировка по queue_time
```

### Проблема: Дубликаты в очереди

**Причина**: Duplicate checking не работает

**Решение**: Используйте `queue_service.join_queue_with_token()` который проверяет дубликаты по phone/telegram_id

---

## 🔌 API Endpoints

### ✅ Активные endpoints (ИСПОЛЬЗУЙТЕ ЭТИ)

**Расположение**: `backend/app/api/v1/endpoints/qr_queue.py`

**Префикс**: `/api/v1/queue/*`

**Основные endpoints**:
- `POST /queue/admin/qr-tokens/generate` - Генерация QR токена для специалиста
- `POST /queue/admin/qr-tokens/generate-clinic` - Генерация общего QR токена для клиники
- `POST /queue/join/start` - Начало сессии присоединения к очереди
- `POST /queue/join/complete` - Завершение присоединения к очереди
- `GET /queue/status/{specialist_id}` - Получение статуса очереди
- `POST /queue/{specialist_id}/call-next` - Вызов следующего пациента
- `GET /queue/admin/queue-analytics/{specialist_id}` - Аналитика очереди
- `PUT /queue/online-entry/{entry_id}/update` - Обновление записи в очереди
- `PUT /queue/online-entry/{entry_id}/full-update` - Полное обновление записи

**Документация**: См. `docs/QUEUE_ENDPOINTS_MIGRATION_GUIDE.md`

### ⚠️ Legacy endpoints (DEPRECATED)

**Расположение**: `backend/app/api/v1/endpoints/queue.py`

**Префикс**: `/api/v1/queue/legacy/*`

**Статус**: DEPRECATED - будут удалены в будущих версиях

**Миграция**: Используйте endpoints из `qr_queue.py` (см. migration guide)

### 🔄 Специализированные endpoints

**Расположение**: `backend/app/api/v1/endpoints/queue_reorder.py`

**Префикс**: `/api/v1/queue/reorder/*`

**Назначение**: Переупорядочение очереди, управление порядком записей

---

## 📚 Связанная документация

- [ONLINE_QUEUE_SYSTEM_IMPLEMENTATION.md](./ONLINE_QUEUE_SYSTEM_IMPLEMENTATION.md) - Полная спецификация
- [QUEUE_ENDPOINTS_MIGRATION_GUIDE.md](./QUEUE_ENDPOINTS_MIGRATION_GUIDE.md) - Migration guide для endpoints
- [QUEUE_REFACTOR_ANALYSIS.md](../QUEUE_REFACTOR_ANALYSIS.md) - Анализ зависимостей
- [PHASE_2_1_COMPLETE_REPORT.md](../PHASE_2_1_COMPLETE_REPORT.md) - Отчет по Foreign Key fix
- [PHASE_3_1_ANALYSIS_REPORT.md](../PHASE_3_1_ANALYSIS_REPORT.md) - Анализ queue endpoints

---

**Подготовил**: Claude Code Agent
**Последнее обновление**: 2025-01-XX
**Статус**: ✅ Официальная документация SSOT
