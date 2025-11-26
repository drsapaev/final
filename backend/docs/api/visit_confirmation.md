# API Документация: Подтверждение Визитов

## Обзор

Система подтверждения визитов позволяет пациентам подтверждать назначенные врачом визиты через различные каналы (Telegram, PWA, телефон). После подтверждения пациенты получают номера в соответствующих очередях.

## Архитектура

```
Врач назначает визит → Генерируется токен подтверждения → Отправляется приглашение → 
Пациент подтверждает → Присваивается номер в очереди (если визит на сегодня)
```

## API Эндпоинты

### 1. Назначение визита врачом

**POST** `/api/v1/doctor/visits/schedule-next`

Создает новый визит в статусе "ожидает подтверждения".

#### Авторизация
- Роли: `Admin`, `Doctor`, `cardio`, `derma`, `dentist`

#### Параметры запроса

```json
{
  "patient_id": 123,
  "service_ids": [1, 2, 3],
  "visit_date": "2025-09-26",
  "visit_time": "14:30",
  "discount_mode": "none|repeat|benefit",
  "all_free": false,
  "confirmation_channel": "telegram|pwa|phone"
}
```

#### Ответ

```json
{
  "visit_id": 456,
  "status": "pending_confirmation",
  "confirmation": {
    "token": "uuid-token-here",
    "expires_at": "2025-09-28T14:30:00Z",
    "channel": "telegram"
  },
  "services": [
    {
      "service_id": 1,
      "name": "Консультация кардиолога",
      "price": 150000.00,
      "discount_amount": 0
    }
  ],
  "total_amount": 150000.00
}
```

#### Коды ошибок

- `400` - Неверные параметры (дата в прошлом, несуществующий пациент/услуга)
- `401` - Не авторизован
- `403` - Недостаточно прав
- `422` - Ошибка валидации данных

---

### 2. Получение информации о визите для подтверждения

**GET** `/api/v1/visits/info/{token}`

Возвращает информацию о визите по токену подтверждения.

#### Параметры
- `token` (path) - Токен подтверждения

#### Ответ

```json
{
  "visit_id": 456,
  "patient_name": "Иванов Иван Иванович",
  "visit_date": "2025-09-26",
  "visit_time": "14:30",
  "services": [
    {
      "name": "Консультация кардиолога",
      "price": 150000.00
    }
  ],
  "total_amount": 150000.00,
  "doctor_name": "Петров П.П.",
  "department": "Кардиология",
  "expires_at": "2025-09-28T14:30:00Z"
}
```

#### Коды ошибок

- `404` - Токен не найден или истек
- `400` - Визит уже подтвержден

---

### 3. Подтверждение визита через Telegram

**POST** `/api/v1/telegram/visits/confirm`

Подтверждает визит через Telegram бот.

#### Параметры запроса

```json
{
  "token": "uuid-token-here",
  "telegram_user_id": "123456789",
  "telegram_username": "patient_username"
}
```

#### Ответ

```json
{
  "success": true,
  "message": "✅ Визит подтвержден! Номера в очередях присвоены.",
  "visit_id": 456,
  "status": "open",
  "patient_name": "Иванов Иван Иванович",
  "visit_date": "2025-09-26",
  "visit_time": "14:30",
  "queue_numbers": [
    {
      "queue_tag": "cardiology_common",
      "number": 15,
      "department": "Кардиология"
    }
  ],
  "print_tickets": [
    {
      "queue_tag": "cardiology_common",
      "ticket_data": "base64-encoded-ticket"
    }
  ]
}
```

---

### 4. Подтверждение визита через PWA

**POST** `/api/v1/patient/visits/confirm`

Подтверждает визит через PWA приложение.

#### Параметры запроса

```json
{
  "token": "uuid-token-here",
  "patient_phone": "+998901234567"
}
```

#### Ответ
Аналогичен Telegram подтверждению.

---

### 5. Подтверждение визита регистратором

**POST** `/api/v1/registrar/visits/{visit_id}/confirm`

Регистратор подтверждает визит по телефону.

#### Авторизация
- Роли: `Admin`, `Registrar`

#### Параметры запроса

```json
{
  "confirmation_notes": "Подтверждено по телефону +998901234567"
}
```

#### Ответ
Аналогичен другим методам подтверждения.

---

## Утреннее присвоение номеров

### 6. Запуск утреннего присвоения

**POST** `/api/v1/admin/morning-assignment/run`

Присваивает номера в очередях всем подтвержденным визитам на текущий день.

#### Авторизация
- Роли: `Admin`

#### Ответ

```json
{
  "success": true,
  "assigned_visits": 25,
  "total_queue_entries": 25,
  "processed_queues": [
    {
      "queue_tag": "cardiology_common",
      "assigned_count": 10
    },
    {
      "queue_tag": "ecg",
      "assigned_count": 8
    },
    {
      "queue_tag": "lab",
      "assigned_count": 7
    }
  ],
  "execution_time": "2.5s"
}
```

### 7. Статистика утреннего присвоения

**GET** `/api/v1/admin/morning-assignment/stats`

Возвращает статистику по подтвержденным визитам и присвоенным номерам.

#### Ответ

```json
{
  "today_confirmed_visits": 25,
  "today_assigned_visits": 20,
  "pending_assignment": 5,
  "total_queue_entries": 20,
  "queues_summary": [
    {
      "queue_tag": "cardiology_common",
      "confirmed_visits": 10,
      "assigned_visits": 8,
      "pending": 2
    }
  ]
}
```

---

## Безопасность

### Rate Limiting

- **Подтверждение визитов**: 5 попыток в минуту с одного IP
- **Получение информации**: 10 запросов в минуту с одного IP
- **Блокировка**: При превышении лимитов IP блокируется на 15 минут

### Токены подтверждения

- **Формат**: UUID v4
- **Время жизни**: 48 часов по умолчанию
- **Одноразовые**: Токен становится недействительным после использования
- **Привязка к каналу**: Токен можно использовать только через указанный канал

### Аудит

Все попытки подтверждения логируются:

```json
{
  "timestamp": "2025-09-25T10:30:00Z",
  "visit_id": 456,
  "token": "uuid-token-here",
  "channel": "telegram",
  "success": true,
  "ip_address": "192.168.1.100",
  "user_agent": "TelegramBot/1.0",
  "error_reason": null
}
```

---

## Коды ошибок

| Код | Описание | Решение |
|-----|----------|---------|
| 400 | Неверный токен или истек срок | Запросить новый токен |
| 401 | Не авторизован | Войти в систему |
| 403 | Недостаточно прав | Обратиться к администратору |
| 404 | Визит не найден | Проверить корректность токена |
| 422 | Ошибка валидации | Исправить данные запроса |
| 429 | Превышен лимит запросов | Подождать и повторить |
| 500 | Внутренняя ошибка сервера | Обратиться к техподдержке |

---

## Примеры использования

### Сценарий 1: Врач назначает визит

```bash
# 1. Врач авторизуется
curl -X POST "http://localhost:8000/api/v1/authentication/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "doctor", "password": "password"}'

# 2. Назначает визит
curl -X POST "http://localhost:8000/api/v1/doctor/visits/schedule-next" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": 123,
    "service_ids": [1],
    "visit_date": "2025-09-26",
    "visit_time": "14:30",
    "discount_mode": "none",
    "all_free": false,
    "confirmation_channel": "telegram"
  }'
```

### Сценарий 2: Пациент подтверждает через Telegram

```bash
# Пациент получает сообщение в Telegram с кнопкой подтверждения
# При нажатии отправляется запрос:
curl -X POST "http://localhost:8000/api/v1/telegram/visits/confirm" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "received-token-from-message",
    "telegram_user_id": "123456789",
    "telegram_username": "patient_username"
  }'
```

### Сценарий 3: Утреннее присвоение номеров

```bash
# Автоматически запускается каждое утро в 07:00
# Или вручную администратором:
curl -X POST "http://localhost:8000/api/v1/admin/morning-assignment/run" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

---

## Интеграция с фронтендом

### React компоненты

- `ScheduleNextModal` - Форма назначения визита врачом
- `VisitConfirmationPage` - Страница подтверждения для PWA
- `QueueAssignmentNotification` - Уведомление о присвоенном номере

### Состояния визита

```javascript
const VISIT_STATUSES = {
  PENDING_CONFIRMATION: 'pending_confirmation',
  CONFIRMED: 'confirmed',
  OPEN: 'open',
  IN_PROGRESS: 'in_progress',
  COMPLETED: 'completed',
  CANCELLED: 'cancelled'
};
```

### Обработка ошибок

```javascript
const handleConfirmationError = (error) => {
  switch (error.status) {
    case 400:
      showError('Токен подтверждения истек. Обратитесь к врачу.');
      break;
    case 404:
      showError('Визит не найден.');
      break;
    case 429:
      showError('Слишком много попыток. Попробуйте позже.');
      break;
    default:
      showError('Произошла ошибка. Обратитесь к администратору.');
  }
};
```
