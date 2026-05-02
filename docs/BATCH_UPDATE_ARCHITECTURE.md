# Batch Update Architecture for Patient Entries

## Проблема

В RegistrarPanel UI строка таблицы представляет **пациента на день**, но API оперирует **отдельными entries** (OnlineQueueEntry, Visit, Appointment):

```
UI Row (1 строка)          →  API Entries (N записей)
┌──────────────────────┐      ┌─────────────────┐
│ Иванов Иван          │      │ OnlineQueueEntry│
│ 17.12.2024           │  →   │ Visit           │
│ K01, D01, L01        │      │ Appointment     │
└──────────────────────┘      └─────────────────┘
```

### Текущие проблемы:

1. **Редактирование**: Изменение одной записи не затрагивает связанные
2. **Отмена**: Требует `aggregated_ids` для групповой отмены
3. **Атомарность**: Нет гарантии, что все операции выполнятся вместе
4. **Performance**: Множество API вызовов вместо одного

---

## Решение: Batch Patient Update API

### Новый endpoint:

```
PATCH /api/v1/registrar/patients/{patient_id}/entries/{date}
```

### Request Body:

```json
{
  "entries": [
    {
      "id": 123,
      "action": "update",
      "service_id": 5,
      "doctor_id": 10,
      "status": "waiting"
    },
    {
      "id": 124,
      "action": "cancel",
      "reason": "Patient request"
    },
    {
      "id": null,
      "action": "create",
      "service_id": 7,
      "specialty": "cardiology"
    }
  ],
  "common_updates": {
    "payment_type": "card",
    "discount_mode": "all_free",
    "approval_status": "approved"
  }
}
```

### Response:

```json
{
  "success": true,
  "patient_id": 42,
  "date": "2024-12-17",
  "updated_entries": [
    {"id": 123, "status": "updated"},
    {"id": 124, "status": "cancelled"},
    {"id": 125, "status": "created"}
  ],
  "aggregated_row": {
    "patient_fio": "Иванов Иван",
    "services": ["K01", "D01"],
    "queue_numbers": [...],
    "total_cost": 150000
  }
}
```

---

## Архитектура

### Backend Structure:

```
backend/app/api/v1/endpoints/
├── registrar_batch.py          # NEW: Batch operations endpoint
└── registrar_integration.py    # Existing endpoint

backend/app/services/
├── batch_patient_service.py    # NEW: Business logic for batch ops
└── queue_service.py            # Existing service
```

### Frontend Integration:

```javascript
// frontend/src/api/registrar.js
export const batchUpdatePatientEntries = async (patientId, date, updates) => {
  return apiRequest('PATCH', `/registrar/patients/${patientId}/entries/${date}`, {
    data: updates
  });
};
```

---

## Фазы имплементации

### Фаза 1: Backend Service (batch_patient_service.py) ✅ DONE
- [x] Создать `BatchPatientService` класс
- [x] Реализовать `update_entries_batch()`
- [x] Добавить транзакционность (rollback при ошибке)
- [ ] Тесты (опционально)

### Фаза 2: API Endpoint (registrar_batch.py) ✅ DONE
- [x] Создать Pydantic схемы для request/response
- [x] Реализовать PATCH endpoint
- [x] Добавить валидацию
- [x] Документация OpenAPI (автоматическая)

### Фаза 3: Frontend Integration ✅ DONE  
- [x] Добавить API клиент (`frontend/src/api/registrarBatch.js`)
- [x] Импорт в `RegistrarPanel.jsx`
- [ ] Обновить `handleComplete` в `AppointmentWizardV2` (опционально)
- [ ] Тестирование

### Фаза 4: Migration 🔄 IN PROGRESS
- [x] TODO комментарии добавлены в код
- [ ] Постепенный переход с одиночных вызовов на batch
- [ ] Deprecation warnings для старых endpoints
- [ ] Мониторинг

---

## Migration Guide

### Для отмены всех записей пациента:

**До (текущая логика):**
```javascript
// Последовательная отмена каждой записи
for (const id of idsToCancel) {
  await api.post(`/visits/${id}/status`, null, { params: { status_new: 'canceled' } });
}
```

**После (batch API):**
```javascript
import { cancelAllPatientEntries, formatDateForAPI } from '../api/registrarBatch';

const result = await cancelAllPatientEntries(
  patientId, 
  formatDateForAPI(date), 
  reason
);

if (result.success) {
  toast.success(`Отменено ${result.cancelled_count} записей`);
}
```

### Для batch-обновления записей:

```javascript
import { batchUpdatePatientEntries, buildBatchRequest } from '../api/registrarBatch';

const request = buildBatchRequest({
  updates: [{ id: 123, status: 'called' }],
  cancels: [124, 125],
  creates: [{ specialty: 'cardiology', service_id: 5 }],
  common: { payment_type: 'card' }
});

const result = await batchUpdatePatientEntries(patientId, date, request);
```

---

## Estimated Timeline

| Фаза | Время | Статус |
|------|-------|--------|
| Фаза 1 | 2-3 часа | ✅ Done |
| Фаза 2 | 1-2 часа | ✅ Done |
| Фаза 3 | 2-3 часа | ✅ Done |
| Фаза 4 | 1 час | 🔄 In Progress |

---

## Созданные файлы

| Файл | Описание |
|------|----------|
| `backend/app/services/batch_patient_service.py` | Business logic |
| `backend/app/api/v1/endpoints/registrar_batch.py` | API endpoints |
| `frontend/src/api/registrarBatch.js` | Frontend client |

## Связанные файлы

- `frontend/src/pages/RegistrarPanel.jsx` - основной потребитель (TODO добавлен)
- `frontend/src/components/wizard/AppointmentWizardV2.jsx` - редактирование
- `backend/app/api/v1/endpoints/registrar_integration.py` - текущие endpoints
- `backend/app/services/queue_service.py` - логика очереди

