# Queue Batch API - Руководство по использованию

**Версия API**: v1
**Endpoint**: `POST /api/v1/registrar-integration/queue/entries/batch`
**Frontend function**: `createQueueEntriesBatch()` из `src/api/queue.js`

---

## 📋 Обзор

Batch Queue API позволяет **массово добавлять услуги** пациенту, который уже находится в очереди.

### Ключевые особенности:

✅ **Сохраняет оригинальный source** - если пациент пришел через QR (source='online'), он остается 'online'
✅ **Справедливое присвоение номера** - queue_time устанавливается на текущее время
✅ **Проверка дубликатов** - не создает повторную очередь к одному специалисту
✅ **Группировка по специалистам** - один специалист = одна запись в очереди (несколько услуг)
✅ **Автосоздание DailyQueue** - создает очередь специалиста если её нет на сегодня

---

## 🎯 Use Case

### Сценарий: Регистратор добавляет услугу пациенту в очереди

**Ситуация**:
1. Пациент Иван сканирует QR-код в 07:30 и встает в очередь к кардиологу
2. Система создает queue entry: `source='online'`, `queue_time=07:30`, `number=1`
3. В 14:10 регистратор видит Ивана в таблице очереди
4. Регистратор решает добавить ему услугу "Общий анализ крови" (лаборатория)

**Ожидаемое поведение**:
- ✅ Создается НОВАЯ очередь для лаборатории
- ✅ Присваивается последний номер (например, №15)
- ✅ **source остается 'online'** (не меняется на 'desk')
- ✅ queue_time = 14:10 (текущее время добавления услуги)

**Почему это важно**:
- Источник 'online' важен для аналитики (сколько пациентов пришло через QR)
- queue_time = 14:10 обеспечивает справедливую очередь (позже всех кто встал раньше)

---

## 🔌 Использование API

### Frontend (JavaScript)

#### 1. Импорт функции

```javascript
import { createQueueEntriesBatch } from '../api/queue';
// или
import { createQueueEntriesBatch } from '../api';
```

#### 2. Базовый пример

```javascript
// Добавить одну услугу пациенту в очереди
const handleAddService = async (patient, service, specialist) => {
  try {
    const result = await createQueueEntriesBatch({
      patientId: patient.id,
      source: patient.source, // 'online', 'desk', или 'morning_assignment'
      services: [
        {
          specialist_id: specialist.id,
          service_id: service.id,
          quantity: 1
        }
      ]
    });

    if (result.success) {
      console.log('✅ Услуга добавлена:', result.entries);
      toast.success(`Добавлено ${result.entries.length} запись(ей) в очередь`);

      // Показать номера очередей
      result.entries.forEach(entry => {
        console.log(`Очередь к специалисту #${entry.specialist_id}: номер ${entry.number}`);
      });
    }
  } catch (error) {
    console.error('❌ Ошибка добавления услуги:', error);
    toast.error('Не удалось добавить услугу в очередь');
  }
};
```

#### 3. Добавление нескольких услуг

```javascript
// Добавить несколько услуг сразу (к разным специалистам)
const handleAddMultipleServices = async (patient, selectedServices) => {
  try {
    const result = await createQueueEntriesBatch({
      patientId: patient.id,
      source: patient.source || 'desk',
      services: selectedServices.map(item => ({
        specialist_id: item.specialist_id,
        service_id: item.service_id,
        quantity: item.quantity || 1
      }))
    });

    if (result.success) {
      toast.success(result.message);
      // Обновить список очередей
      refreshQueueData();
    }
  } catch (error) {
    toast.error('Ошибка: ' + (error.response?.data?.detail || error.message));
  }
};
```

#### 4. Пример с UI компонентом

```javascript
const AddServiceButton = ({ queueEntry }) => {
  const [showDialog, setShowDialog] = useState(false);
  const [selectedService, setSelectedService] = useState(null);
  const [selectedSpecialist, setSelectedSpecialist] = useState(null);

  const handleConfirm = async () => {
    try {
      const result = await createQueueEntriesBatch({
        patientId: queueEntry.patient_id,
        source: queueEntry.source, // ⭐ Сохраняем оригинальный source
        services: [
          {
            specialist_id: selectedSpecialist.id,
            service_id: selectedService.id,
            quantity: 1
          }
        ]
      });

      if (result.success) {
        toast.success('Услуга успешно добавлена!');
        setShowDialog(false);
        // Обновить таблицу очередей
        onRefresh?.();
      }
    } catch (error) {
      toast.error('Ошибка добавления услуги');
    }
  };

  return (
    <>
      <Button
        variant="outline"
        size="sm"
        onClick={() => setShowDialog(true)}
      >
        Добавить услугу
      </Button>

      <AddServiceDialog
        isOpen={showDialog}
        onClose={() => setShowDialog(false)}
        onConfirm={handleConfirm}
        patient={queueEntry}
        onServiceSelect={setSelectedService}
        onSpecialistSelect={setSelectedSpecialist}
      />
    </>
  );
};
```

---

### Backend (Python)

#### Прямой вызов через HTTP

```python
import requests

def add_services_to_queue(patient_id: int, source: str, services: list):
    """Добавить услуги пациенту в очереди"""
    url = "http://localhost:18000/api/v1/registrar-integration/queue/entries/batch"

    payload = {
        "patient_id": patient_id,
        "source": source,  # 'online', 'desk', 'morning_assignment'
        "services": services  # [{"specialist_id": 1, "service_id": 10, "quantity": 1}]
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()

    return response.json()


# Пример использования
result = add_services_to_queue(
    patient_id=123,
    source="online",
    services=[
        {"specialist_id": 5, "service_id": 42, "quantity": 1},  # Лаборатория
        {"specialist_id": 2, "service_id": 15, "quantity": 2}   # Процедуры (2 шт)
    ]
)

print(f"Создано записей: {len(result['entries'])}")
for entry in result["entries"]:
    print(f"  - Специалист #{entry['specialist_id']}: номер {entry['number']}")
```

#### Использование в FastAPI endpoint

```python
from app.api.v1.endpoints.registrar_integration import router
from app.schemas.queue import BatchQueueEntriesRequest

@router.post("/my-custom-endpoint")
async def custom_queue_operation(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Кастомная операция с очередью"""

    # Подготовить данные
    request_data = BatchQueueEntriesRequest(
        patient_id=patient_id,
        source="desk",
        services=[
            BatchServiceItem(specialist_id=1, service_id=10, quantity=1)
        ]
    )

    # Вызвать batch endpoint напрямую
    from app.api.v1.endpoints.registrar_integration import create_queue_entries_batch

    result = create_queue_entries_batch(
        request=request_data,
        db=db,
        current_user=current_user
    )

    return result
```

---

## 📝 API Reference

### Request

**Endpoint**: `POST /api/v1/registrar-integration/queue/entries/batch`

**Headers**:
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Body** (JSON):

```typescript
{
  patient_id: number,        // ID пациента (обязательно)
  source: string,            // 'online' | 'desk' | 'morning_assignment' (обязательно)
  services: Array<{          // Массив услуг (обязательно, min 1)
    specialist_id: number,   // ID специалиста (обязательно)
    service_id: number,      // ID услуги (обязательно)
    quantity: number         // Количество (по умолчанию: 1)
  }>
}
```

**Пример запроса**:

```json
{
  "patient_id": 123,
  "source": "online",
  "services": [
    {
      "specialist_id": 5,
      "service_id": 42,
      "quantity": 1
    },
    {
      "specialist_id": 2,
      "service_id": 15,
      "quantity": 2
    }
  ]
}
```

---

### Response

**Success** (200 OK):

```typescript
{
  success: boolean,          // true
  entries: Array<{
    specialist_id: number,   // ID специалиста
    queue_id: number,        // ID очереди (DailyQueue)
    number: int,             // Присвоенный номер
    queue_time: string       // ISO timestamp
  }>,
  message: string            // Сообщение (на русском)
}
```

**Пример успешного ответа**:

```json
{
  "success": true,
  "entries": [
    {
      "specialist_id": 5,
      "queue_id": 12,
      "number": 15,
      "queue_time": "2025-11-25T14:10:33+05:00"
    },
    {
      "specialist_id": 2,
      "queue_id": 8,
      "number": 7,
      "queue_time": "2025-11-25T14:10:33+05:00"
    }
  ],
  "message": "Создано 2 запись(ей) в очереди"
}
```

---

**Error** (400/404/500):

```typescript
{
  detail: string             // Описание ошибки
}
```

**Примеры ошибок**:

```json
// Пациент не найден
{
  "detail": "Пациент с ID 999 не найден"
}

// Услуга не найдена
{
  "detail": "Услуга с ID 999 не найдена"
}

// Специалист не найден
{
  "detail": "Специалист с ID 999 не найден"
}

// Дубликат (уже в очереди)
// Примечание: Это НЕ ошибка! Endpoint возвращает success=true и существующую запись
{
  "success": true,
  "entries": [
    {
      "specialist_id": 5,
      "queue_id": 12,
      "number": 10,  // Существующий номер
      "queue_time": "2025-11-25T07:30:00+05:00"  // Оригинальное время
    }
  ],
  "message": "Создано 1 запись(ей) в очереди (1 уже существовала)"
}
```

---

## ⚙️ Бизнес-логика

### Обработка дубликатов

**Правило**: Если пациент УЖЕ в очереди к специалисту на сегодня (status='waiting' или 'called'), НЕ создается новая запись.

**Поведение**:
- Endpoint возвращает `success: true`
- В массиве `entries` возвращается существующая запись
- Сообщение указывает: "1 уже существовала"

**Пример**:

```javascript
// Пациент уже в очереди к кардиологу
const result = await createQueueEntriesBatch({
  patientId: 123,
  source: 'desk',
  services: [
    { specialist_id: 1, service_id: 10, quantity: 1 }  // Кардиолог
  ]
});

// result = {
//   success: true,
//   entries: [
//     { specialist_id: 1, queue_id: 5, number: 3, queue_time: "07:30" }
//   ],
//   message: "Создано 1 запись(ей) в очереди (1 уже существовала)"
// }
```

---

### Группировка по специалистам

**Правило**: Несколько услуг одного специалиста = одна запись в очереди.

**Пример**:

```javascript
// Запрос: 3 услуги кардиолога
const result = await createQueueEntriesBatch({
  patientId: 123,
  source: 'desk',
  services: [
    { specialist_id: 1, service_id: 10, quantity: 1 },  // ЭКГ
    { specialist_id: 1, service_id: 11, quantity: 1 },  // ЭхоКГ
    { specialist_id: 1, service_id: 12, quantity: 1 }   // Консультация
  ]
});

// Результат: ОДНА запись в очереди (номер 5)
// entries = [
//   { specialist_id: 1, queue_id: 5, number: 5, queue_time: "..." }
// ]
```

---

### Автосоздание DailyQueue

**Правило**: Если очередь специалиста не существует на сегодня, она создается автоматически.

**Параметры автосоздания**:
- `day`: Текущая дата в Tashkent timezone
- `specialist_id`: ID специалиста
- `is_clinic_wide`: `false` (персональная очередь)
- `max_capacity`: `null` (без ограничений)

**Логи**:
```
INFO: Очередь для специалиста 5 не найдена на 2025-11-25, создаю новую...
INFO: ✅ Создана новая очередь ID=15 для специалиста 5 на 2025-11-25
```

---

## 🔒 Права доступа

### Требуемые роли:

- ✅ **Admin** - полный доступ
- ✅ **Registrar** - полный доступ
- ❌ **Doctor** - нет доступа
- ❌ **Patient** - нет доступа

### Проверка авторизации:

```python
@router.post("/registrar-integration/queue/entries/batch")
def create_queue_entries_batch(
    request: BatchQueueEntriesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))  # ⭐
):
    ...
```

**Ошибка при отсутствии прав**:
```json
{
  "detail": "Not enough permissions"
}
```

---

## 🧪 Тестирование

### Curl примеры

#### 1. Базовый запрос

```bash
curl -X POST "http://localhost:18000/api/v1/registrar-integration/queue/entries/batch" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": 123,
    "source": "online",
    "services": [
      {
        "specialist_id": 1,
        "service_id": 10,
        "quantity": 1
      }
    ]
  }'
```

#### 2. Несколько услуг

```bash
curl -X POST "http://localhost:18000/api/v1/registrar-integration/queue/entries/batch" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": 123,
    "source": "desk",
    "services": [
      {"specialist_id": 1, "service_id": 10, "quantity": 1},
      {"specialist_id": 2, "service_id": 15, "quantity": 2},
      {"specialist_id": 5, "service_id": 42, "quantity": 1}
    ]
  }'
```

---

### Python test script

```python
import requests

BASE_URL = "http://localhost:18000"
ACCESS_TOKEN = "your_access_token_here"

def test_batch_queue_creation():
    """Тест создания очередей batch методом"""

    # Шаг 1: Создать тестового пациента (или использовать существующего)
    patient_id = 123  # Замените на реальный ID

    # Шаг 2: Вызвать batch endpoint
    response = requests.post(
        f"{BASE_URL}/api/v1/registrar-integration/queue/entries/batch",
        json={
            "patient_id": patient_id,
            "source": "online",
            "services": [
                {"specialist_id": 1, "service_id": 10, "quantity": 1}
            ]
        },
        headers={
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
    )

    # Шаг 3: Проверить результат
    assert response.status_code == 200, f"Ошибка: {response.status_code}"

    result = response.json()
    assert result["success"] == True
    assert len(result["entries"]) > 0

    print("✅ Тест пройден!")
    print(f"Создано записей: {len(result['entries'])}")
    for entry in result["entries"]:
        print(f"  - Специалист #{entry['specialist_id']}: номер {entry['number']}")

if __name__ == "__main__":
    test_batch_queue_creation()
```

---

## 🎨 UI Integration Ideas

### Вариант 1: Кнопка "Добавить услугу" в таблице очередей

**Местоположение**: RegistrarPanel, вкладка "Онлайн-очередь"

```javascript
<EnhancedAppointmentsTable
  data={queueData}
  actions={[
    {
      key: 'add_service',
      label: 'Добавить услугу',
      icon: <Plus />,
      onClick: (row) => {
        setSelectedPatient(row);
        setShowAddServiceDialog(true);
      }
    }
  ]}
/>

<AddServiceDialog
  isOpen={showAddServiceDialog}
  patient={selectedPatient}
  onConfirm={async (service, specialist) => {
    await createQueueEntriesBatch({
      patientId: selectedPatient.patient_id,
      source: selectedPatient.source,
      services: [{
        specialist_id: specialist.id,
        service_id: service.id,
        quantity: 1
      }]
    });
  }}
/>
```

---

### Вариант 2: Контекстное меню

```javascript
<AppointmentContextMenu
  row={selectedRow}
  actions={[
    {
      key: 'add_service',
      label: 'Добавить услугу',
      onClick: () => handleAddService(selectedRow)
    }
  ]}
/>
```

---

### Вариант 3: Batch добавление для нескольких пациентов

```javascript
const handleBulkAddService = async (selectedPatients, service, specialist) => {
  const promises = selectedPatients.map(patient =>
    createQueueEntriesBatch({
      patientId: patient.id,
      source: patient.source,
      services: [{
        specialist_id: specialist.id,
        service_id: service.id,
        quantity: 1
      }]
    })
  );

  const results = await Promise.allSettled(promises);

  const succeeded = results.filter(r => r.status === 'fulfilled').length;
  toast.success(`Добавлено услуг: ${succeeded} из ${selectedPatients.length}`);
};
```

---

## 📊 Source Badges (Визуализация источника)

### Рекомендуемые цвета:

```css
.source-badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
}

.source-badge.online {
  background-color: #e3f2fd;  /* Светло-синий */
  color: #1976d2;
}

.source-badge.desk {
  background-color: #f3e5f5;  /* Светло-фиолетовый */
  color: #7b1fa2;
}

.source-badge.morning_assignment {
  background-color: #fff3e0;  /* Светло-оранжевый */
  color: #f57c00;
}
```

### React компонент:

```javascript
const SourceBadge = ({ source }) => {
  const labels = {
    online: 'QR-код',
    desk: 'Регистратура',
    morning_assignment: 'Утреннее распределение'
  };

  return (
    <span className={`source-badge ${source}`}>
      {labels[source] || source}
    </span>
  );
};
```

---

## 🔗 Связанная документация

- [PHASE_4_FRONTEND_INTEGRATION_REPORT.md](../PHASE_4_FRONTEND_INTEGRATION_REPORT.md) - Отчет по интеграции
- [PHASE_3_2_COMPLETE_REPORT.md](../PHASE_3_2_COMPLETE_REPORT.md) - Backend implementation
- [ONLINE_QUEUE_SYSTEM_IMPLEMENTATION.md](./ONLINE_QUEUE_SYSTEM_IMPLEMENTATION.md) - Полная спецификация

---

## 💡 Best Practices

### 1. Всегда сохраняйте оригинальный source

❌ **Неправильно**:
```javascript
await createQueueEntriesBatch({
  patientId: patient.id,
  source: 'desk',  // Хардкод!
  services: [...]
});
```

✅ **Правильно**:
```javascript
await createQueueEntriesBatch({
  patientId: patient.id,
  source: patient.source || 'desk',  // Используем оригинальный source
  services: [...]
});
```

---

### 2. Обрабатывайте ошибки gracefully

```javascript
try {
  const result = await createQueueEntriesBatch({...});
  toast.success(result.message);
} catch (error) {
  // Детальное сообщение
  const errorMsg = error.response?.data?.detail || error.message || 'Неизвестная ошибка';
  toast.error(`Не удалось добавить услугу: ${errorMsg}`);

  // Логирование
  console.error('Batch queue error:', {
    patient: patientId,
    services,
    error: errorMsg
  });
}
```

---

### 3. Обновляйте UI после успешного добавления

```javascript
const handleAddService = async (...) => {
  const result = await createQueueEntriesBatch({...});

  if (result.success) {
    // Обновить таблицу очередей
    refreshQueueData();

    // Показать номера
    result.entries.forEach(entry => {
      console.log(`Очередь #${entry.queue_id}: номер ${entry.number}`);
    });

    // Отправить WebSocket update (если есть)
    websocket?.send(JSON.stringify({
      type: 'queue_updated',
      queue_ids: result.entries.map(e => e.queue_id)
    }));
  }
};
```

---

### 4. Валидация перед отправкой

```javascript
const validateBatchRequest = (patientId, source, services) => {
  if (!patientId || patientId <= 0) {
    throw new Error('Некорректный ID пациента');
  }

  if (!['online', 'desk', 'morning_assignment'].includes(source)) {
    throw new Error('Некорректный source (должен быть online/desk/morning_assignment)');
  }

  if (!Array.isArray(services) || services.length === 0) {
    throw new Error('Список услуг пуст');
  }

  services.forEach((service, index) => {
    if (!service.specialist_id || !service.service_id) {
      throw new Error(`Услуга #${index + 1}: отсутствует specialist_id или service_id`);
    }
  });
};

// Использование
try {
  validateBatchRequest(patientId, source, services);
  const result = await createQueueEntriesBatch({...});
} catch (error) {
  toast.error(error.message);
}
```

---

## ❓ FAQ

### Q: Можно ли добавить услугу пациенту, которого нет в очереди?

**A**: Да! Endpoint создает очередь автоматически. Но убедитесь что:
- Пациент существует в БД (patient_id валиден)
- Специалист существует (specialist_id валиден)
- Услуга существует (service_id валиден)

---

### Q: Что делать если пациент уже в очереди к специалисту?

**A**: Endpoint возвращает существующую запись с `success: true`. Проверьте сообщение:
```javascript
if (result.message.includes('уже существовала')) {
  console.log('Пациент уже в очереди');
}
```

---

### Q: Как изменить source для существующей очереди?

**A**: Batch endpoint НЕ меняет source у существующих записей. Если нужно изменить source:
1. Используйте отдельный PATCH endpoint (если существует)
2. Или удалите старую запись и создайте новую

---

### Q: Можно ли добавить несколько услуг одного специалиста?

**A**: Да! Они будут сгруппированы в одну запись очереди:
```javascript
services: [
  { specialist_id: 1, service_id: 10, quantity: 1 },
  { specialist_id: 1, service_id: 11, quantity: 1 },
  { specialist_id: 1, service_id: 12, quantity: 1 }
]
// → Одна запись в очереди (номер X) с тремя услугами
```

---

### Q: Как узнать номер в очереди после добавления?

**A**: Номер возвращается в ответе:
```javascript
const result = await createQueueEntriesBatch({...});
result.entries.forEach(entry => {
  console.log(`Номер в очереди: ${entry.number}`);
});
```

---

## 🎓 Заключение

Batch Queue API предоставляет гибкий способ добавления услуг пациентам в очереди с **сохранением оригинального источника регистрации** и **справедливым присвоением номера**.

**Ключевые преимущества**:
- ✅ Простой API
- ✅ Автоматическая группировка услуг
- ✅ Обработка дубликатов
- ✅ Автосоздание очередей
- ✅ Детальные логи

**Готово к использованию**:
- ✅ Backend endpoint реализован
- ✅ Frontend API client готов
- ✅ Документация создана
- ⏳ UI integration - по требованию

---

**Авторы**: Backend Team, Frontend Team
**Дата обновления**: 2025-11-25
**Версия**: 1.0
