# Migration Guide: Queue Endpoints

**Дата создания**: 2025-01-XX  
**Статус**: Актуально  
**Версия API**: v1

---

## 📋 Обзор

Этот документ описывает миграцию с legacy queue endpoints (`/queue/legacy/*`) на новые endpoints в `qr_queue.py` и `queue_reorder.py`.

### Почему миграция?

- ✅ **Расширенная функциональность** - новые endpoints поддерживают больше возможностей
- ✅ **Лучшая архитектура** - разделение по функциональности (QR, reorder, legacy)
- ✅ **Исправлены routing conflicts** - каждый router на своем префиксе
- ✅ **Активная поддержка** - legacy endpoints будут удалены в будущих версиях

---

## 🔄 Маппинг Endpoints

### 1. Генерация QR токена

#### ❌ Legacy (DEPRECATED)
```
POST /api/v1/queue/legacy/qrcode
Query params:
  - day: date (YYYY-MM-DD)
  - specialist_id: int
```

#### ✅ Новый (Рекомендуется)
```
POST /api/v1/queue/admin/qr-tokens/generate
Body:
{
  "specialist_id": int,
  "department": str,
  "expires_hours": int (default: 24),
  "target_date": str (optional, YYYY-MM-DD),
  "visit_type": str (default: "paid")
}
```

**Преимущества**:
- Поддержка `expires_hours` для настройки времени жизни токена
- Поддержка `visit_type` (paid/repeat/benefit)
- Поддержка `target_date` для планирования
- Возвращает `qr_code_base64` для прямого отображения

**Пример миграции**:
```python
# Старый код
response = requests.post(
    f"{API_URL}/queue/legacy/qrcode",
    params={"day": "2025-01-15", "specialist_id": 123}
)

# Новый код
response = requests.post(
    f"{API_URL}/queue/admin/qr-tokens/generate",
    json={
        "specialist_id": 123,
        "department": "cardiology",
        "target_date": "2025-01-15",
        "expires_hours": 24
    }
)
```

---

### 2. Вступление в очередь

#### ❌ Legacy (DEPRECATED)
```
POST /api/v1/queue/legacy/join
Body:
{
  "token": str,
  "phone": str (optional),
  "telegram_id": str (optional),
  "patient_name": str (optional)
}
```

#### ✅ Новый (Рекомендуется)
```
POST /api/v1/queue/join/start
Body:
{
  "token": str
}

POST /api/v1/queue/join/complete
Body:
{
  "session_token": str,
  "patient_name": str,
  "phone": str,
  "telegram_id": int (optional),
  "specialist_ids": List[int] (optional, для множественного присоединения)
}
```

**Преимущества**:
- **Session-based подход** - более безопасный и гибкий
- **Множественное присоединение** - можно записаться к нескольким специалистам одновременно
- **Лучшая валидация** - двухэтапный процесс с проверками

**Пример миграции**:
```python
# Старый код
response = requests.post(
    f"{API_URL}/queue/legacy/join",
    json={
        "token": "abc123",
        "phone": "+998901234567",
        "patient_name": "Иван Иванов"
    }
)

# Новый код
# Шаг 1: Начать сессию
session_response = requests.post(
    f"{API_URL}/queue/join/start",
    json={"token": "abc123"}
)
session_token = session_response.json()["session_token"]

# Шаг 2: Завершить присоединение
join_response = requests.post(
    f"{API_URL}/queue/join/complete",
    json={
        "session_token": session_token,
        "patient_name": "Иван Иванов",
        "phone": "+998901234567"
    }
)
```

---

### 3. Получение статистики очереди

#### ❌ Legacy (DEPRECATED)
```
GET /api/v1/queue/legacy/statistics/{specialist_id}
```

#### ✅ Новый (Рекомендуется)
```
GET /api/v1/queue/admin/queue-analytics/{specialist_id}
```

**Преимущества**:
- Более детальная аналитика
- Поддержка фильтров по датам
- Дополнительные метрики

---

### 4. Открытие приема

#### ❌ Legacy (DEPRECATED)
```
POST /api/v1/queue/legacy/open
Query params:
  - day: date
  - specialist_id: int
```

#### ✅ Новый (Рекомендуется)
```
POST /api/v1/queue/{specialist_id}/open
Body:
{
  "day": str (YYYY-MM-DD)
}
```

**Примечание**: Этот endpoint может быть в другом модуле. Проверьте документацию.

---

### 5. Получение статуса очереди

#### ❌ Legacy (DEPRECATED)
```
GET /api/v1/queue/legacy/today
Query params:
  - specialist_id: int
```

#### ✅ Новый (Рекомендуется)
```
GET /api/v1/queue/status/{specialist_id}
```

**Преимущества**:
- Более структурированный ответ
- Дополнительная информация о состоянии очереди

---

### 6. Вызов пациента

#### ❌ Legacy (DEPRECATED)
```
POST /api/v1/queue/legacy/call/{entry_id}
```

#### ✅ Новый (Рекомендуется)
```
POST /api/v1/queue/{specialist_id}/call-next
```

**Преимущества**:
- Автоматический вызов следующего пациента
- Не нужно указывать `entry_id` вручную
- Более безопасный (проверка прав на уровне специалиста)

---

## 🔧 Переупорядочение очереди

### Новые endpoints (queue_reorder.py)

Все endpoints для переупорядочения находятся под префиксом `/queue/reorder`:

```
PUT /api/v1/queue/reorder/reorder
PUT /api/v1/queue/reorder/move-entry
GET /api/v1/queue/reorder/status/by-specialist/
GET /api/v1/queue/reorder/status/{queue_id}
```

**Примечание**: Эти endpoints не имеют legacy аналогов, они новые.

---

## ⚠️ Deprecation Timeline

### Текущая версия (v1.0)
- ✅ Legacy endpoints доступны под `/queue/legacy/*`
- ✅ Новые endpoints доступны под `/queue/*` и `/queue/reorder/*`
- ⚠️ Legacy endpoints возвращают deprecation warnings в headers

### Будущие версии
- **v1.1** (Q2 2025): Deprecation warnings в response body
- **v1.2** (Q3 2025): Legacy endpoints удалены

---

## 📝 Checklist для миграции

- [ ] Идентифицировать все использования legacy endpoints
- [ ] Обновить API клиенты на новые endpoints
- [ ] Обновить frontend компоненты
- [ ] Протестировать новую функциональность
- [ ] Обновить документацию
- [ ] Мониторить использование legacy endpoints
- [ ] Планировать удаление legacy кода после миграции

---

## 🆘 Поддержка

При возникновении проблем с миграцией:

1. Проверьте документацию API: `/docs` (Swagger UI)
2. Проверьте примеры в этом документе
3. Создайте issue в репозитории проекта

---

## 📚 Дополнительные ресурсы

- [Queue System Architecture](./QUEUE_SYSTEM_ARCHITECTURE.md)
- [Online Queue Implementation](./ONLINE_QUEUE_SYSTEM_IMPLEMENTATION.md)
- [API Documentation](../backend/app/api/v1/endpoints/qr_queue.py)

