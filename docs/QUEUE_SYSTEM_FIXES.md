# 🔧 Исправления системы очередей

> **Historical Fix Report**
> Этот документ отражает прошлую волну исправлений и не должен использоваться как актуальный queue SSOT.
> Текущий источник истины: `docs/QUEUE_SYSTEM_ARCHITECTURE.md`, `docs/PANEL_QA_CHECKLIST.md`, `docs/runbooks/LOCAL_STAGING_ACCEPTANCE_RUNBOOK.md`.

**Дата**: 2025-10-01
**Версия**: 1.0

---

## 📋 Обзор исправлений

### 1️⃣ **Разделение визитов по отделениям**

**Проблема**: Один пациент с услугами из разных отделений (например, K01 + L01) создавал один визит с department="cardiology", содержащий все услуги.

**Решение**: Изменена группировка в `groupCartItemsByVisit()` в `AppointmentWizardV2.jsx`:

```javascript
// БЫЛО:
const key = `${item.doctor_id || 'no_doctor'}_${item.visit_date}_${item.visit_time || 'no_time'}`;

// СТАЛО:
const department = getDepartmentByService(item.service_id);
const key = `${department}_${item.doctor_id || 'no_doctor'}_${item.visit_date}_${item.visit_time || 'no_time'}`;
```

**Результат**: Создаются отдельные визиты для каждого отделения.

---

### 2️⃣ **Независимая нумерация очередей**

**Проблема**: Нумерация была корректной (через `enumerate`), но визиты не разделялись по отделениям (см. п.1).

**Решение**: После исправления группировки, каждое отделение автоматически получило независимую нумерацию.

**Пример**:
- Пациент с услугами K01 + L01:
  - В кардиологии: свой номер (например, №3)
  - В лаборатории: свой номер (например, №1)

---

### 3️⃣ **Статус визитов от регистратора**

**Проблема**: Визиты от регистратора создавались со статусом `pending_confirmation` из-за фича-флага `confirmation_before_queue`, и не попадали в очередь.

**Решение**: Изменена логика в `registrar_wizard.py`:

```python
# БЫЛО:
confirmation_required = is_feature_enabled(db, "confirmation_before_queue", default=True)
if confirmation_required and cart_data.discount_mode != "all_free":
    visit_status = "pending_confirmation"
else:
    visit_status = "confirmed"

# СТАЛО:
# Регистратор всегда создаёт подтверждённые записи
visit_status = "confirmed"
confirmed_at = datetime.utcnow()
confirmed_by = f"registrar_{current_user.id}"
```

**Результат**: Визиты от регистратора сразу попадают в очередь.

---

### 4️⃣ **Отображение времени регистрации**

**Проблема 1**: Поле `created_at` не передавалось на верхний уровень объекта appointment в `RegistrarPanel.jsx`.

**Решение**: Добавлено поле `created_at` во все места создания объектов appointments:

```javascript
const appointment = {
  id: entry.id,
  // ... другие поля ...
  created_at: entry.created_at,  // ✅ Добавлено
  queue_numbers: [{
    // ...
    created_at: entry.created_at
  }]
};
```

**Проблема 2**: Backend отправлял время без указания timezone, JavaScript интерпретировал как локальное время.

**Решение**: Добавлен суффикс 'Z' к ISO строке в `registrar_integration.py`:

```python
# БЫЛО:
"created_at": entry_wrapper["created_at"].isoformat() if entry_wrapper["created_at"] else None

# СТАЛО:
"created_at": entry_wrapper["created_at"].isoformat() + "Z" if entry_wrapper["created_at"] else None
```

**Результат**: Фронтенд правильно конвертирует UTC время в локальное (+5 часов для Узбекистана).

---

### 5️⃣ **Микрозадержка между визитами**

**Проблема**: Все визиты одного пациента создавались с одинаковым `created_at`, что могло вызвать проблемы с сортировкой.

**Решение**: Добавлена микрозадержка в `registrar_wizard.py`:

```python
from time import sleep

for idx, visit_req in enumerate(cart_data.visits):
    if idx > 0:
        sleep(0.001)  # 1 миллисекунда задержки
    
    # Создание визита...
```

**Результат**: Каждый визит имеет уникальное время создания.

---

## 🧪 Тестирование

### Сценарий 1: Создание записи с услугами из разных отделений

1. Создать запись на пациента с услугами K01 (кардиология) + L01 (лаборатория)
2. **Ожидается**:
   - 2 визита в БД (один для кардиологии, один для лаборатории)
   - В вкладке "Кардиология": пациент с номером N
   - В вкладке "Лаборатория": тот же пациент с номером M (независимым от N)

### Сценарий 2: Проверка времени

1. Создать запись
2. **Ожидается**: В столбце "Дата" отображается локальное время создания (UTC+5)

### Сценарий 3: Очередь на сегодня

1. Создать несколько записей через регистратора
2. **Ожидается**: Все записи сразу видны в очереди (без необходимости подтверждения)

---

## 📝 Важные замечания

### Timezone

- **Backend хранит**: UTC время (без timezone info)
- **Backend отправляет**: ISO строку с суффиксом 'Z' (например, `2025-10-01T02:55:09.203953Z`)
- **Frontend отображает**: Локальное время (JavaScript автоматически конвертирует)

### Статусы визитов

- `pending_confirmation`: Ожидает подтверждения (для онлайн-записей)
- `confirmed`: Подтверждён (записи от регистратора, подтверждённые онлайн-записи)
- `open`: Открыт для приёма (после присвоения номера очереди)

### Группировка визитов

Визиты группируются по ключу:
```javascript
`${department}_${doctor_id}_${visit_date}_${visit_time}`
```

Это означает, что один пациент с услугами из разных отделений создаст несколько визитов.

---

## 🔗 Связанные файлы

**Backend:**
- `backend/app/api/v1/endpoints/registrar_wizard.py` - создание визитов
- `backend/app/api/v1/endpoints/registrar_integration.py` - получение очередей

**Frontend:**
- `frontend/src/components/wizard/AppointmentWizardV2.jsx` - группировка визитов
- `frontend/src/pages/RegistrarPanel.jsx` - отображение очередей
- `frontend/src/components/tables/EnhancedAppointmentsTable.jsx` - таблица с временем

---

## ✅ Контрольный список

При изменении системы очередей проверьте:

- [ ] Визиты правильно группируются по department
- [ ] Нумерация независима для каждого отделения
- [ ] Время отправляется с суффиксом 'Z'
- [ ] Поле `created_at` присутствует на верхнем уровне appointment
- [ ] Визиты от регистратора имеют status='confirmed'
- [ ] Микрозадержка между визитами работает

---

**Автор**: AI Agent  
**Версия документа**: 1.0

