# Queue API Reference

**Дата создания**: 2025-01-XX  
**Статус**: Актуально  
**Версия API**: v1

---

## 📋 Обзор

Этот документ содержит полное описание всех API endpoints для работы с системой очередей.

### Структура endpoints

- **Активные endpoints** (`qr_queue.py`): `/api/v1/queue/*`
- **Legacy endpoints** (`queue.py`): `/api/v1/queue/legacy/*` (DEPRECATED)
- **Reorder endpoints** (`queue_reorder.py`): `/api/v1/queue/reorder/*`

---

## ✅ Активные Endpoints (qr_queue.py)

### 1. Генерация QR токенов

#### `POST /api/v1/queue/admin/qr-tokens/generate`

Генерирует QR токен для конкретного специалиста.

**Требуемые роли**: `Admin`, `Registrar`

**Request Body**:
```json
{
  "specialist_id": 123,
  "department": "cardiology",
  "expires_hours": 24,
  "target_date": "2025-01-15",
  "visit_type": "paid"
}
```

**Response** (200 OK):
```json
{
  "token": "abc123...",
  "qr_url": "https://clinic.com/queue/join?token=abc123...",
  "qr_code_base64": "data:image/png;base64,iVBORw0KG...",
  "expires_at": "2025-01-16T07:00:00Z",
  "specialist_name": "Иванов Иван",
  "day": "2025-01-15"
}
```

**Ошибки**:
- `400 Bad Request` - Некорректные параметры
- `403 Forbidden` - Недостаточно прав
- `404 Not Found` - Специалист не найден

---

#### `POST /api/v1/queue/admin/qr-tokens/generate-clinic`

Генерирует общий QR токен для всей клиники. Пациент сможет выбрать несколько специалистов после сканирования.

**Требуемые роли**: `Admin`, `Registrar`

**Request Body**:
```json
{
  "expires_hours": 24,
  "target_date": "2025-01-15"
}
```

**Response** (200 OK):
```json
{
  "token": "clinic_abc123...",
  "qr_url": "https://clinic.com/queue/join?token=clinic_abc123...",
  "qr_code_base64": "data:image/png;base64,iVBORw0KG...",
  "is_clinic_wide": true,
  "day": "2025-01-15",
  "expires_at": "2025-01-16T07:00:00Z",
  "active": true
}
```

---

### 2. Управление QR токенами

#### `GET /api/v1/queue/admin/qr-tokens/active`

Получает список всех активных QR токенов.

**Требуемые роли**: `Admin`, `Registrar`

**Response** (200 OK):
```json
[
  {
    "token": "abc123...",
    "specialist_id": 123,
    "specialist_name": "Иванов Иван",
    "is_clinic_wide": false,
    "expires_at": "2025-01-16T07:00:00Z",
    "usage_count": 5,
    "created_at": "2025-01-15T07:00:00Z"
  }
]
```

---

#### `GET /api/v1/queue/qr-tokens/{token}/info`

Получает информацию о конкретном QR токене.

**Параметры**:
- `token` (path) - Токен для проверки

**Response** (200 OK):
```json
{
  "token": "abc123...",
  "is_valid": true,
  "is_expired": false,
  "specialist_id": 123,
  "specialist_name": "Иванов Иван",
  "is_clinic_wide": false,
  "expires_at": "2025-01-16T07:00:00Z",
  "usage_count": 5
}
```

**Ошибки**:
- `404 Not Found` - Токен не найден

---

#### `DELETE /api/v1/queue/admin/qr-tokens/{token}`

Удаляет QR токен.

**Требуемые роли**: `Admin`, `Registrar`

**Параметры**:
- `token` (path) - Токен для удаления

**Response** (200 OK):
```json
{
  "success": true,
  "message": "QR токен удален"
}
```

---

### 3. Присоединение к очереди

#### `POST /api/v1/queue/join/start`

Начинает сессию присоединения к очереди (первый этап двухэтапного процесса).

**Request Body**:
```json
{
  "token": "abc123..."
}
```

**Response** (200 OK):
```json
{
  "session_token": "session_xyz789...",
  "token_valid": true,
  "specialist_id": 123,
  "specialist_name": "Иванов Иван",
  "is_clinic_wide": false,
  "available_specialists": [
    {
      "id": 123,
      "name": "Иванов Иван",
      "specialty": "cardiology"
    }
  ],
  "expires_at": "2025-01-15T08:00:00Z"
}
```

**Ошибки**:
- `400 Bad Request` - Неверный токен
- `404 Not Found` - Токен не найден или истек

---

#### `POST /api/v1/queue/join/complete`

Завершает присоединение к очереди (второй этап).

**Request Body**:
```json
{
  "session_token": "session_xyz789...",
  "patient_name": "Петров Петр",
  "phone": "+998901234567",
  "telegram_id": 123456789,
  "specialist_ids": [123]
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Вы записаны в очередь",
  "entries": [
    {
      "queue_id": 456,
      "number": 5,
      "specialist_id": 123,
      "specialist_name": "Иванов Иван",
      "queue_time": "2025-01-15T08:30:00Z"
    }
  ]
}
```

**Ошибки**:
- `400 Bad Request` - Неверная сессия или данные
- `409 Conflict` - Дубликат записи (пациент уже в очереди)

---

### 4. Получение информации об очереди

#### `GET /api/v1/queue/status/{specialist_id}`

Получает текущий статус очереди для специалиста.

**Требуемые роли**: `Admin`, `Doctor`, `Registrar`

**Параметры**:
- `specialist_id` (path) - ID специалиста
- `target_date` (query, optional) - Дата (YYYY-MM-DD), по умолчанию сегодня

**Response** (200 OK):
```json
{
  "queue_id": 456,
  "day": "2025-01-15",
  "specialist_name": "Иванов Иван",
  "is_open": true,
  "opened_at": "2025-01-15T07:00:00Z",
  "total_entries": 10,
  "waiting_entries": 8,
  "entries": [
    {
      "id": 789,
      "number": 1,
      "patient_name": "Петров Петр",
      "phone": "+998901234567",
      "status": "waiting",
      "created_at": "2025-01-15T07:05:00Z",
      "called_at": null
    }
  ]
}
```

---

#### `GET /api/v1/queue/available-specialists`

Получает список доступных специалистов для записи.

**Параметры**:
- `date` (query, optional) - Дата (YYYY-MM-DD), по умолчанию сегодня
- `department` (query, optional) - Фильтр по отделению

**Response** (200 OK):
```json
[
  {
    "id": 123,
    "name": "Иванов Иван",
    "specialty": "cardiology",
    "department": "cardiology",
    "available": true,
    "current_queue_size": 5
  }
]
```

---

### 5. Управление очередью

#### `POST /api/v1/queue/{specialist_id}/call-next`

Вызывает следующего пациента из очереди.

**Требуемые роли**: `Admin`, `Doctor`, `Registrar`

**Параметры**:
- `specialist_id` (path) - ID специалиста

**Response** (200 OK):
```json
{
  "success": true,
  "entry": {
    "id": 789,
    "number": 1,
    "patient_name": "Петров Петр",
    "phone": "+998901234567",
    "called_at": "2025-01-15T08:00:00Z"
  },
  "message": "Пациент №1 вызван"
}
```

**Ошибки**:
- `404 Not Found` - Очередь пуста или не найдена

---

### 6. Управление записями в очереди

#### `PUT /api/v1/queue/online-entry/{entry_id}/update`

Обновляет запись в очереди (частичное обновление).

**Требуемые роли**: `Admin`, `Registrar`, `Doctor`, `cardio`, `derma`, `dentist`

**Параметры**:
- `entry_id` (path) - ID записи

**Request Body**:
```json
{
  "patient_name": "Петров Петр",
  "phone": "+998901234567"
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Запись обновлена",
  "entry": {
    "id": 789,
    "number": 1,
    "patient_name": "Петров Петр",
    "phone": "+998901234567"
  }
}
```

---

#### `PUT /api/v1/queue/online-entry/{entry_id}/full-update`

Полное обновление записи в очереди (включая услуги, скидки и т.д.).

**Требуемые роли**: `Admin`, `Registrar`, `Doctor`, `cardio`, `derma`, `dentist`

**Параметры**:
- `entry_id` (path) - ID записи

**Request Body**:
```json
{
  "patient_name": "Петров Петр",
  "phone": "+998901234567",
  "birth_year": 1990,
  "address": "Ташкент, ул. Примерная, 1",
  "services": ["A01.001", "A02.001"],
  "service_codes": ["A01.001", "A02.001"],
  "discount_mode": "repeat",
  "visit_type": "paid",
  "all_free": false
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Запись успешно обновлена",
  "entry": {
    "id": 789,
    "patient_name": "Петров Петр",
    "phone": "+998901234567",
    "services": ["A01.001", "A02.001"],
    "total_amount": 50000.0,
    "discount_mode": "repeat"
  }
}
```

---

#### `POST /api/v1/queue/online-entry/{entry_id}/cancel-service`

Отменяет услугу в записи очереди.

**Требуемые роли**: `Admin`, `Registrar`, `Doctor`

**Параметры**:
- `entry_id` (path) - ID записи

**Request Body**:
```json
{
  "service_code": "A01.001"
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Услуга отменена",
  "entry": {
    "id": 789,
    "services": ["A02.001"]
  }
}
```

---

### 7. Аналитика

#### `GET /api/v1/queue/admin/queue-analytics/{specialist_id}`

Получает аналитику по очереди специалиста.

**Требуемые роли**: `Admin`, `Registrar`

**Параметры**:
- `specialist_id` (path) - ID специалиста
- `date_from` (query, optional) - Начальная дата
- `date_to` (query, optional) - Конечная дата

**Response** (200 OK):
```json
{
  "specialist_id": 123,
  "specialist_name": "Иванов Иван",
  "period": {
    "from": "2025-01-01",
    "to": "2025-01-15"
  },
  "statistics": {
    "total_entries": 150,
    "waiting": 10,
    "called": 120,
    "completed": 100,
    "cancelled": 20,
    "average_wait_time": "15 минут"
  }
}
```

---

## ⚠️ Legacy Endpoints (DEPRECATED)

Все endpoints из `queue.py` помечены как DEPRECATED и будут удалены в будущих версиях.

**Префикс**: `/api/v1/queue/legacy/*`

**Миграция**: См. `docs/QUEUE_ENDPOINTS_MIGRATION_GUIDE.md`

---

## 🔄 Reorder Endpoints

**Префикс**: `/api/v1/queue/reorder/*`

Endpoints для переупорядочения очереди. См. `queue_reorder.py` для деталей.

---

## 📝 Общие замечания

### Аутентификация

Все endpoints (кроме публичных) требуют JWT токен в заголовке:
```
Authorization: Bearer <token>
```

### Обработка ошибок

Все ошибки возвращаются в формате:
```json
{
  "error": "error_code",
  "message": "Человекочитаемое сообщение",
  "detail": "Детали ошибки"
}
```

### Коды статусов

- `200 OK` - Успешный запрос
- `400 Bad Request` - Некорректные параметры
- `401 Unauthorized` - Требуется аутентификация
- `403 Forbidden` - Недостаточно прав
- `404 Not Found` - Ресурс не найден
- `409 Conflict` - Конфликт (дубликат, лимит и т.д.)
- `422 Unprocessable Entity` - Ошибка валидации
- `500 Internal Server Error` - Внутренняя ошибка сервера

---

## 📚 Связанная документация

- [QUEUE_ENDPOINTS_MIGRATION_GUIDE.md](./QUEUE_ENDPOINTS_MIGRATION_GUIDE.md) - Migration guide
- [QUEUE_SYSTEM_ARCHITECTURE.md](./QUEUE_SYSTEM_ARCHITECTURE.md) - Архитектура системы
- [ONLINE_QUEUE_SYSTEM_IMPLEMENTATION.md](./ONLINE_QUEUE_SYSTEM_IMPLEMENTATION.md) - Полная спецификация

---

**Подготовил**: Claude Code Agent  
**Последнее обновление**: 2025-01-XX  
**Статус**: ✅ Актуально

