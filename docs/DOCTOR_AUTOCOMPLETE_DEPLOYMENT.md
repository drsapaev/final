# Doctor History Autocomplete - Deployment Guide

## Обзор

Этот гайд описывает процесс деплоя системы автодополнения на основе истории врача (Doctor History-Based Autocomplete).

---

## Предварительные требования

1. **Backend**: Python 3.9+, SQLAlchemy
2. **Frontend**: React 18+
3. **Database**: PostgreSQL или SQLite
4. **Migrations**: Alembic

---

## Шаг 1: Database Migration

### 1.1 Применить миграцию

```bash
cd c:\final\backend
alembic upgrade head
```

### 1.2 Проверить таблицу

```sql
SELECT * FROM doctor_phrase_history LIMIT 1;
```

**Ожидаемые колонки:**
- `id`, `doctor_id`, `field`, `phrase`
- `prefix_3`, `prefix_5`
- `usage_count`, `last_used`, `first_used`
- `specialty`
- `suggestions_shown`, `suggestions_accepted` (telemetry)

### 1.3 Если миграция не сработала (SQLite)

Для SQLite можно добавить колонки вручную:

```bash
python c:\final\backend\update_phrase_table.py
```

---

## Шаг 2: Batch Indexing (Initial Data)

### 2.1 Через скрипт (рекомендуется)

```bash
cd c:\final\backend
python migrate_phrases.py
```

**Вывод:**
```
🚀 Starting EMR Phrase Migration...
🔍 Searching for doctors with EMR records...

✅ Migration Finished!
-----------------------------------
Total Doctors Processed: 50
Total EMRs Indexed:     523
Total Unique Phrases:   2150
Doctors Now Ready:      35
Duration:              12500 ms
-----------------------------------
```

### 2.2 Через API (ADMIN ONLY)

```bash
curl -X POST http://localhost:8000/api/v1/emr/batch-index \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "limit": 100,
    "offset": 0
  }'
```

### 2.3 Для конкретного врача

```bash
curl -X POST http://localhost:8000/api/v1/emr/index-doctor \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "doctorId": 123,
    "specialty": "cardiology"
  }'
```

---

## Шаг 3: Проверка Readiness

### 3.1 Через API

```bash
curl http://localhost:8000/api/v1/emr/readiness/123
```

**Response (готов):**
```json
{
  "ready": true,
  "progress": {
    "completed_emrs": 15,
    "unique_phrases": 45,
    "repeated_phrases": 12
  },
  "missing": [],
  "message": "Autocomplete ready!"
}
```

**Response (не готов):**
```json
{
  "ready": false,
  "progress": {
    "completed_emrs": 5,
    "unique_phrases": 12,
    "repeated_phrases": 2
  },
  "missing": [
    "Needs 5 more EMRs (10 required)",
    "Needs 18 more unique phrases (30 required)",
    "Needs 3 more repeated phrases (5 required)"
  ],
  "message": "Not ready yet"
}
```

---

## Шаг 4: Frontend Deployment

### 4.1 Build

```bash
cd c:\final\frontend
npm run build
```

### 4.2 Проверка сборки

Убедитесь, что в `dist/` есть:
- `index.html`
- `assets/index-*.js`
- `assets/index-*.css`

---

## Шаг 5: Incremental Indexing

Автоматическая индексация уже интегрирована в:

**Backend: `app/api/v1/endpoints/appointment_flow.py`**

```python
@router.post("/{appointment_id}/emr/save")
def save_emr(...):
    # ... сохранение EMR ...
    
    # 🔥 Автоматическая индексация
    indexer.index_single_emr(
        emr_id=saved_emr.id,
        doctor_id=current_user.id,
        specialty=specialty
    )
    
    return saved_emr
```

**Проверка:**
1. Создайте новую EMR через веб-интерфейс
2. Сохраните её (не черновик)
3. Проверьте, что фразы добавились в БД:

```sql
SELECT * FROM doctor_phrase_history 
WHERE doctor_id = 123 
ORDER BY last_used DESC 
LIMIT 10;
```

---

## Шаг 6: Monitoring

### 6.1 Telemetry Dashboard

```bash
curl http://localhost:8000/api/v1/emr/telemetry-stats/123
```

**Response:**
```json
{
  "doctorId": 123,
  "totalShown": 150,
  "totalAccepted": 120,
  "acceptanceRate": 80.0,
  "avgTimeToAcceptMs": null,
  "topAcceptedPhrases": [
    {
      "phrase": "Головная боль, давящего характера...",
      "field": "complaints",
      "timesAccepted": 23
    }
  ]
}
```

### 6.2 Database Stats

```sql
-- Топ врачей по количеству фраз
SELECT 
  doctor_id,
  COUNT(*) as phrase_count,
  SUM(usage_count) as total_usages
FROM doctor_phrase_history
GROUP BY doctor_id
ORDER BY phrase_count DESC
LIMIT 10;

-- Топ полей
SELECT 
  field,
  COUNT(DISTINCT doctor_id) as doctors_count,
  COUNT(*) as phrase_count
FROM doctor_phrase_history
GROUP BY field
ORDER BY phrase_count DESC;
```

---

## Troubleshooting

### Проблема: "no such column: suggestions_shown"

**Решение:**
```bash
python c:\final\backend\update_phrase_table.py
```

### Проблема: "type object 'EMR' has no attribute 'created_by'"

**Решение:** Убедитесь, что используется актуальная версия `emr_phrase_indexer.py`, где врач достаётся через `Appointment.doctor_id`.

### Проблема: Подсказки не появляются во фронтенде

**Диагностика:**
1. Проверьте `ready` в DevTools Console:
   ```javascript
   // В консоли браузера
   console.log('History ready:', ready);
   ```
2. Проверьте кэш readiness (TTL 1 минута)
3. Проверьте, что `useDoctorHistory={true}` и `doctorId` передан в `EMRSmartField`

### Проблема: Врач не становится "ready" после индексации

**Диагностика:**
```sql
-- Проверить количество фраз
SELECT 
  COUNT(*) as total_phrases,
  COUNT(DISTINCT phrase) as unique_phrases,
  SUM(CASE WHEN usage_count > 1 THEN 1 ELSE 0 END) as repeated_phrases
FROM doctor_phrase_history
WHERE doctor_id = 123;
```

Убедитесь:
- `unique_phrases >= 30`
- `repeated_phrases >= 5`
- Врач завершил >= 10 EMR (не черновиков)

---

## Performance Optimization

### 1. Database Indexes

Уже созданы в миграции:
```sql
CREATE INDEX ix_doctor_phrase_prefix_3 
  ON doctor_phrase_history (doctor_id, field, prefix_3);

CREATE INDEX ix_doctor_phrase_prefix_5 
  ON doctor_phrase_history (doctor_id, field, prefix_5);
```

### 2. Readiness Cache

Frontend кэширует результат на 1 минуту. Для инвалидации:
```javascript
recheckReadiness(); // в useDoctorPhrases hook
```

### 3. Cleanup Old Phrases

Периодически запускайте cleanup:

```python
from app.services.emr_phrase_indexer import get_emr_phrase_indexer

indexer = get_emr_phrase_indexer(db)
deleted = indexer.cleanup_old_phrases(
    doctor_id=123,
    max_age_days=365,
    min_usage=1
)
print(f"Deleted {deleted} old phrases")
```

---

## Security Checklist

- ✅ Endpoint `/batch-index` доступен только для Admin
- ✅ Каждый врач видит только свою историю (`doctor_id` фильтр)
- ✅ Telemetry не содержит медицинских данных (только ID фраз)
- ✅ Нет генерации текста — только поиск в истории

---

## Rollback Plan

Если нужно откатить фичу:

1. **Frontend:** Установить `useDoctorHistory={false}` в `EMRSmartField`
2. **Backend:** Закомментировать индексацию в `save_emr()`
3. **Database:** Не удалять таблицу — можно будет вернуться позже

```sql
-- Опционально: очистить данные
TRUNCATE TABLE doctor_phrase_history;
```

---

## Next Steps

1. **Мониторинг acceptance rate** через telemetry dashboard
2. **Настройка Celery** для batch-индексации в фоне
3. **A/B тестирование** эффективности подсказок
4. **Расширение полей** (добавить `procedures`, `medications`)

---

*Version: 1.0*  
*Last Updated: 2026-01-06*
