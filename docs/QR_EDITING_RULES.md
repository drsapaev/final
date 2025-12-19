# Правила Редактирования QR-Записей (SSOT)

Этот документ описывает строгие правила обработки и редактирования QR-записей (записей онлайн-очереди) в системе, направленные на предотвращение дублирования и поддержание целостности данных.

## 1. Идентификация QR-записи

Запись считается QR-записью (OnlineQueueEntry), если выполняются следующие условия:
*   `record_type === 'online_queue'`
*   `source === 'online'`

## 2. Принцип Единого Источника Истины (SSOT) при Редактировании

При редактировании QR-записи через `AppointmentWizardV2` (или любые другие интерфейсы) **ЗАПРЕЩЕНО** создавать новые записи в БД. Необходимо обновлять существующую запись.

### Правило 2.1: Использование endpoint полного обновления
Для сохранения изменений в QR-записи **ОБЯЗАТЕЛЬНО** использовать метод API:
`PUT /api/v1/qr-queue/online-entry/{entry_id}/full-update`

Этот метод обновляет:
*   Данные пациента (ФИО, телефон, год рождения, адрес)
*   Тип визита и скидки
*   Список услуг (удаляет старые, добавляет новые)

### Правило 2.2: Запрет на использование `create_cart_appointments`
При редактировании существующей QR-записи **ЗАПРЕЩЕНО** использовать endpoint `POST /registrar/cart` (`create_cart_appointments`), так как он всегда создает *новые* записи в очереди и визиты, что приводит к дубликатам.

## 3. Логика Frontend (AppointmentWizardV2)

Логика `handleComplete` в `AppointmentWizardV2.jsx` должна следовать следующему алгоритму:

1.  **Проверка типа записи:**
    ```javascript
    const isOnlineQueueEntry = initialData.record_type === 'online_queue' && effectiveSource === 'online';
    ```

2.  **Получение ID:**
    ```javascript
    const queueEntryId = initialData.queue_numbers?.[0]?.id || initialData.id;
    ```

3.  **Выполнение обновления:**
    Если `isOnlineQueueEntry` и `queueEntryId` существуют:
    *   Сформировать payload с данными пациента и услугами из корзины.
    *   Вызвать `updateOnlineQueueEntry` (wrapper для `PUT .../full-update`).
    *   **CRITICAL:** При успешном обновлении немедленно завершить функцию (`return`), чтобы предотвратить выполнение fallback-логики создания записей.

## 4. Дедупликация в Таблице (RegistrarPanel)

При отображении списка записей в `RegistrarPanel` необходимо группировать записи, чтобы предотвратить визуальное дублирование, если один пациент записан к нескольким врачам через QR (хотя технически это разные записи или одна запись с несколькими услугами).

**Ключ дедупликации:**
`dedupKey = online_{pid|phone|fio}_{date}`

*   Приоритет 1: `patient_id`
*   Приоритет 2: `phone` (нормализованный)
*   Приоритет 3: `fio` (нормализованный)
*   Fallback: `entry_id` (если ничего не совпадает)

## 5. Добавление Услуг

При добавлении услуги к существующей QR-записи:
*   Новая услуга добавляется в список услуг существующей `OnlineQueueEntry` через `full-update`.
*   Система **НЕ ДОЛЖНА** создавать отдельную `OnlineQueueEntry` для новой услуги, если это не требуется бизнес-логикой (например, запись к другому специалисту на другое время). В текущей реализации все услуги в рамках одного QR-визита хранятся в одной записи (или связанных записях с единым `visit_id`).

## 6. SSOT для Service Code Mappings (Декабрь 2024)

Для унификации обработки услуг и кодов создан централизованный модуль:

**Файл:** `frontend/src/utils/serviceCodeResolver.js`

### Экспортируемые константы:
```javascript
export const SPECIALTY_TO_CODE = { ... };    // specialty → service code
export const CODE_TO_NAME = { ... };          // code → display name
export const LEGACY_CODE_TO_NAME = { ... };   // legacy codes
export const ID_TO_NAME = { ... };            // numeric ID → name
```

### Ключевые функции:
```javascript
// Извлечение услуг из initialData (5 источников → 1 формат)
export function normalizeServicesFromInitialData(initialData, servicesData);

// Получение отображаемого имени
export function getServiceDisplayName(code);

// Преобразование specialty → service code
export function toServiceCode(value);
```

### Использование в AppointmentWizardV2:
```javascript
import { normalizeServicesFromInitialData } from '../../utils/serviceCodeResolver';

// Вместо 130 строк разбора — одна функция:
const items = normalizeServicesFromInitialData(initialData, servicesData);
```

## 7. Batch API для групповых операций (Декабрь 2024)

Для атомарных операций над всеми записями пациента за день:

**Backend:** `/api/v1/registrar/batch/patients/{patient_id}/entries/{date}`

**Frontend:** `frontend/src/api/registrarBatch.js`

```javascript
import { cancelAllPatientEntries, batchUpdatePatientEntries } from '../api/registrarBatch';

// Отмена всех записей пациента
await cancelAllPatientEntries(patientId, date, reason);

// Batch-обновление
await batchUpdatePatientEntries(patientId, date, {
  entries: [
    { id: 123, action: 'update', status: 'called' },
    { id: 124, action: 'cancel', reason: 'no show' }
  ]
});
```

**Документация:** `docs/BATCH_UPDATE_ARCHITECTURE.md`

---

## 8. Правила отображения кодов услуг (Декабрь 2024)

### Проблема
Ранее система неправильно отображала коды услуг: вместо правильных кодов (K11 для ЭхоКГ, L02 для Гемоглобин) показывались fallback-коды (K01, L01).

### Решение: Приоритет API-данных

**ПРАВИЛО:** `appointment.services` из API всегда имеют приоритет над fallback-логикой.

```javascript
// ✅ ПРАВИЛЬНО: Используем данные из API
if (appointment.services && appointment.services.length > 0) {
  return appointment.services; // ["K11", "L02"]
}

// ❌ НЕПРАВИЛЬНО: Генерация из specialty (приводит к K01)
const code = toServiceCode(specialty); // Fallback на K01
```

### Маппинг отделов и кодов услуг

| Вкладка | Коды услуг | Примеры |
|---------|-----------|---------|
| **Кардиолог** | K (кроме K10) | K01 (консультация), K11 (ЭхоКГ) |
| **ЭКГ** | K10, ECG* | K10 (ЭКГ), ECG01 |
| **Дерматолог** | D | D01 (консультация) |
| **Стоматолог** | S | S01 (консультация), S10 (рентген зубов) |
| **Лаборатория** | L | L01, L02, L11, L20, L23, L65 |
| **Процедуры** | P, C, D_PROC | P01-P05, C01-C12, D_PROC01-D_PROC04 |

### Ключевые файлы

- `frontend/src/pages/RegistrarPanel.jsx`:
  - `filterServicesByDepartment()` — фильтрация услуг по вкладке
  - `isInDepartment()` — определение принадлежности записи к отделу
- `frontend/src/utils/serviceCodeResolver.js`:
  - `getServiceDisplayName()` — название по коду
  - `toServiceCode()` — преобразование specialty → code

---

## 9. Критические фиксы QR-очередей (Декабрь 2025)

### 9.1 Проблема

При QR-регистрации и последующем редактировании в регистратуре возникали:
- **Дублирующиеся записи** вместо обновления существующих
- **Неправильное `queue_time`** для новых услуг
- **Пустые entries** (без услуг) засоряли БД
- **`patient_id` не создавался** при QR-регистрации
- **`visit_id` не создавался** при первом заполнении QR-записи

### 9.2 Реализованные фиксы

#### Fix 1: Создание `patient_id` при QR-регистрации ✅

**Файл:** `backend/app/services/qr_queue_service.py`

**Новый метод:** `_find_or_create_patient(patient_name, phone)`

Гарантирует, что `patient_id` **ВСЕГДА** заполняется при QR-регистрации.

#### Fix 2: Создание `Visit` при первом заполнении QR-записи ✅

**Файл:** `backend/app/services/qr_queue_service.py` + `backend/app/api/v1/endpoints/qr_queue.py`

**Новый метод:** `_create_visit_for_qr(patient_id, visit_date, services, ...)`

При первом добавлении услуг к QR-записи автоматически создаётся Visit с VisitServices.

#### Fix 3: Backend вычисляет `aggregated_ids` ✅

Backend **САМ** вычисляет `aggregated_ids` по `patient_id` + дате. Frontend `aggregated_ids` используется только как fallback.

#### Fix 4: Запрет создания entries без услуг ✅

Перед созданием новой `OnlineQueueEntry` — проверка на пустой `services_list_new`.

#### Fix 5: Правильное `queue_time` для "первого заполнения" QR ✅

| Сценарий | `is_first_fill_qr` | `queue_time` для услуг |
|----------|-------------------|----------------------|
| QR → пустая entry → регистратор добавляет услуги | `True` | **Оригинальное** (время QR) |
| QR → услуги есть → регистратор добавляет новые | `False` | **Текущее** (время редактирования) |

---

## 📅 Changelog

| Дата | Изменение |
|------|-----------|
| 2025-12-19 | **Добавлены критические фиксы QR-очередей (секция 9)** |
| 2025-12-19 | Fix 1-5: patient_id, visit_id, aggregated_ids, queue_time |
| 2024-12-18 | Добавлена секция 8: Правила отображения кодов услуг |
| 2024-12-18 | Исправлено: K11 теперь правильно отображается вместо K01 |
| 2024-12-18 | Исправлено: filterServicesByDepartment использует API-данные |
| 2024-12-17 | Добавлена секция SSOT (serviceCodeResolver.js) |
| 2024-12-17 | Добавлена секция Batch API |
| 2024-12-17 | Исправлена дедупликация по entry.id вместо specialty |

*Последнее обновление: 2025-12-19*

