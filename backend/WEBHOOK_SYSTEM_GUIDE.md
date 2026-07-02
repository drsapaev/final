# Система Webhook'ов - Руководство

## Обзор

Система webhook'ов позволяет интегрировать клинику с внешними системами через HTTP callbacks. При возникновении определенных событий в системе (создание пациента, завершение визита, платеж и т.д.), webhook'и автоматически отправляют уведомления на указанные URL.

## Основные возможности

### 🔗 Управление Webhook'ами
- **Создание и настройка** webhook'ов с гибкими параметрами
- **Активация/деактивация** webhook'ов
- **Фильтрация событий** по типу и условиям
- **Настройка повторов** при ошибках
- **Безопасность** через HMAC подписи

### 📊 Мониторинг и Аналитика
- **Статистика вызовов** в реальном времени
- **Логирование всех попыток** с деталями ответов
- **Анализ производительности** и успешности
- **Уведомления об ошибках**

### 🔄 Надежность
- **Автоматические повторы** при неудачных вызовах
- **Экспоненциальная задержка** между повторами
- **Таймауты и лимиты** для защиты системы
- **Очередь событий** для обработки в фоне

## Типы Событий

### Пациенты
- `patient.created` - Создан новый пациент
- `patient.updated` - Обновлена информация о пациенте
- `patient.deleted` - Пациент удален

### Записи и Визиты
- `appointment.created` - Создана новая запись
- `appointment.updated` - Запись изменена
- `appointment.cancelled` - Запись отменена
- `appointment.completed` - Запись завершена
- `visit.created` - Создан новый визит
- `visit.updated` - Визит обновлен
- `visit.completed` - Визит завершен

### Очереди
- `queue.entry_created` - Пациент встал в очередь
- `queue.entry_updated` - Статус в очереди изменен
- `queue.entry_called` - Пациент вызван
- `queue.entry_completed` - Прием завершен

### Платежи
- `payment.created` - Создан платеж
- `payment.completed` - Платеж завершен
- `payment.failed` - Платеж не прошел
- `payment.refunded` - Платеж возвращен

### Пользователи
- `user.created` - Создан новый пользователь
- `user.updated` - Пользователь обновлен
- `user.deleted` - Пользователь удален

### Системные События
- `system.backup_completed` - Резервное копирование завершено
- `system.backup_failed` - Ошибка резервного копирования
- `system.maintenance_start` - Начало технического обслуживания
- `system.maintenance_end` - Конец технического обслуживания

## API Endpoints

### Управление Webhook'ами

#### Создание Webhook'а
```http
POST /api/v1/webhooks/
Content-Type: application/json
Authorization: Bearer <token>

{
  "name": "Интеграция с CRM",
  "description": "Отправка данных о пациентах в CRM систему",
  "url": "https://crm.example.com/webhooks/patients",
  "events": ["patient.created", "patient.updated"],
  "headers": {
    "X-API-Key": "your-api-key"
  },
  "secret": "webhook-secret-key",
  "max_retries": 3,
  "retry_delay": 60,
  "timeout": 30,
  "filters": {
    "department": "cardiology"
  }
}
```

#### Получение Списка Webhook'ов
```http
GET /api/v1/webhooks/?status=active&limit=50
Authorization: Bearer <token>
```

#### Обновление Webhook'а
```http
PUT /api/v1/webhooks/{webhook_id}
Content-Type: application/json
Authorization: Bearer <token>

{
  "name": "Обновленное название",
  "is_active": true
}
```

#### Активация/Деактивация
```http
POST /api/v1/webhooks/{webhook_id}/activate
Authorization: Bearer <token>

POST /api/v1/webhooks/{webhook_id}/deactivate
Authorization: Bearer <token>
```

#### Тестирование Webhook'а
```http
POST /api/v1/webhooks/{webhook_id}/test
Content-Type: application/json
Authorization: Bearer <token>

{
  "webhook_id": 1,
  "event_type": "patient.created",
  "test_data": {
    "patient_id": 123,
    "name": "Тестовый Пациент"
  }
}
```

### Мониторинг

#### Статистика Webhook'а
```http
GET /api/v1/webhooks/{webhook_id}/stats
Authorization: Bearer <token>
```

#### Системная Статистика
```http
GET /api/v1/webhooks/system/stats
Authorization: Bearer <token>
```

#### Вызовы Webhook'а
```http
GET /api/v1/webhooks/{webhook_id}/calls?limit=100
Authorization: Bearer <token>
```

### События

#### Ручной Триггер События
```http
POST /api/v1/webhooks/events/trigger
Content-Type: application/json
Authorization: Bearer <token>

{
  "event_type": "patient.created",
  "event_data": {
    "patient_id": 123,
    "name": "Иван Иванов",
    "phone": "+7900123456"
  },
  "source": "manual",
  "correlation_id": "manual-trigger-001"
}
```

## Формат Webhook Payload

Каждый webhook получает стандартизированный JSON payload:

```json
{
  "event_type": "patient.created",
  "event_data": {
    "patient_id": 123,
    "name": "Иван Иванов",
    "phone": "+7900123456",
    "email": "ivan@example.com",
    "created_at": "2024-01-15T10:30:00Z"
  },
  "webhook_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T10:30:05Z",
  "attempt": 1
}
```

### Заголовки

Каждый webhook запрос содержит следующие заголовки:

```http
Content-Type: application/json
User-Agent: MediLab-Webhook/1.0
X-Webhook-Event: patient.created
X-Webhook-ID: 550e8400-e29b-41d4-a716-446655440000
X-Webhook-Attempt: 1
X-Webhook-Signature: sha256=abc123... (если настроен secret)
```

## Безопасность

### HMAC Подпись

Если для webhook'а настроен `secret`, каждый запрос подписывается HMAC-SHA256:

```python
import hmac
import hashlib

def verify_signature(payload, signature, secret):
    expected = hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return signature == f"sha256={expected}"
```

### Проверка на Стороне Получателя

```javascript
const crypto = require('crypto');

function verifyWebhook(payload, signature, secret) {
    const expectedSignature = crypto
        .createHmac('sha256', secret)
        .update(payload)
        .digest('hex');
    
    return signature === `sha256=${expectedSignature}`;
}
```

## Обработка Ошибок и Повторы

### Логика Повторов

1. **Первая попытка** - немедленно
2. **Повторы** - с задержкой (по умолчанию 60 секунд)
3. **Максимум попыток** - настраивается (по умолчанию 3)
4. **Статусы успеха** - HTTP 200-299
5. **Статусы ошибок** - HTTP 400+ или сетевые ошибки

### Экспоненциальная Задержка

```
Попытка 1: немедленно
Попытка 2: через 60 секунд
Попытка 3: через 120 секунд
Попытка 4: через 240 секунд
```

## Фильтрация Событий

Webhook'и могут фильтровать события по различным критериям:

```json
{
  "filters": {
    "department": "cardiology",
    "patient_type": "new",
    "amount_min": 1000
  }
}
```

Событие будет отправлено только если все условия фильтра выполнены.

## Лимиты и Ограничения

- **Максимум повторов**: 10
- **Таймаут запроса**: 300 секунд
- **Размер payload**: 10MB
- **Размер ответа**: 10KB (для логирования)
- **Количество webhook'ов**: без ограничений
- **Частота вызовов**: без ограничений

## Мониторинг и Алерты

### Метрики

- Общее количество вызовов
- Успешные вызовы
- Неудачные вызовы
- Среднее время ответа
- Процент успешности

### Автоматические Алерты

- Webhook неактивен более 24 часов
- Процент успешности ниже 90%
- Более 10 неудачных попыток подряд
- Превышение таймаута

## Примеры Интеграций

### 1. CRM Система

```json
{
  "name": "CRM Integration",
  "url": "https://crm.company.com/api/webhooks/patients",
  "events": ["patient.created", "patient.updated"],
  "headers": {
    "Authorization": "Bearer crm-api-token"
  }
}
```

### 2. Система Уведомлений

```json
{
  "name": "SMS Notifications",
  "url": "https://sms.provider.com/webhooks/appointments",
  "events": ["appointment.created", "appointment.cancelled"],
  "filters": {
    "notification_enabled": true
  }
}
```

### 3. Аналитическая Система

```json
{
  "name": "Analytics Dashboard",
  "url": "https://analytics.company.com/api/events",
  "events": ["visit.completed", "payment.completed"],
  "headers": {
    "X-Analytics-Key": "analytics-key"
  }
}
```

## Отладка и Тестирование

### Тестовые События

Используйте тестовые webhook'и для отладки:

```bash
curl -X POST "http://localhost:18000/api/v1/webhooks/1/test" \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "webhook_id": 1,
    "event_type": "patient.created",
    "test_data": {"test": true}
  }'
```

### Логирование

Все вызовы webhook'ов логируются с деталями:
- URL и метод
- Заголовки запроса
- Payload
- Статус ответа
- Время выполнения
- Ошибки

### Webhook.site для Тестирования

Используйте https://webhook.site для получения тестового URL и просмотра входящих webhook'ов.

## Производительность

### Асинхронная Обработка

Все webhook'и обрабатываются асинхронно в фоне, не блокируя основные операции системы.

### Батчинг

Для высоконагруженных систем рекомендуется группировать события и отправлять их батчами.

### Кэширование

Конфигурации webhook'ов кэшируются для быстрого доступа.

## Миграция и Обновления

### Версионирование

Webhook payload поддерживает версионирование для обратной совместимости.

### Graceful Shutdown

При обновлении системы все активные webhook'и завершаются корректно.

## Поддержка

Для получения поддержки по системе webhook'ов:

1. Проверьте логи вызовов в админ-панели
2. Используйте тестовые webhook'и для отладки
3. Проверьте статистику и метрики
4. Обратитесь к документации API

---

*Система webhook'ов обеспечивает надежную интеграцию с внешними системами и позволяет создавать мощные автоматизированные рабочие процессы.*

