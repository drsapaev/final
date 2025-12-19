# Система онлайн-очередей - Полная документация реализации

## 📋 Содержание

1. [Обзор системы](#обзор-системы)
2. [Архитектура и принципы работы](#архитектура-и-принципы-работы)
3. [База данных](#база-данных)
4. [API Endpoints](#api-endpoints)
5. [Frontend компоненты](#frontend-компоненты)
6. [Сценарии использования](#сценарии-использования)
7. [Технические детали](#технические-детали)
8. [Миграции БД](#миграции-бд)

---

## Обзор системы

### Цель системы

Система онлайн-очередей позволяет пациентам регистрироваться в очереди двумя способами:

1. **Онлайн через QR-код** (ранняя регистрация до открытия клиники)
2. **В регистратуре вручную** (после открытия клиники)

### Ключевые особенности

- ✅ Один общий QR-код для всей клиники
- ✅ Множественный выбор специалистов при QR-регистрации
- ✅ Отдельные позиции в очереди для каждой услуги
- ✅ Справедливая система приоритетов на основе времени регистрации
- ✅ Гибридное редактирование: обновление данных без изменения времени очереди
- ✅ Автоматическая блокировка QR после открытия клиники
- ✅ Визуальные метки источника регистрации (QR/Manual)

---

## Архитектура и принципы работы

### Основные принципы

#### 1. Приоритет на основе времени регистрации

Каждая запись в очереди имеет собственное поле `queue_time`, которое:
- Фиксируется в момент создания записи
- Никогда не изменяется при редактировании данных пациента
- Определяет позицию в очереди (чем раньше время - тем выше приоритет)

#### 2. Множественные очереди для одного пациента

Один пациент может иметь несколько записей в очереди:
- По одной записи на каждую услугу/специалиста
- Каждая запись имеет свой `queue_time`
- При QR-регистрации нескольких услуг - все получают одинаковое время

#### 3. Гибридное редактирование

При редактировании пациента в регистратуре:
- **Личные данные** (ФИО, телефон, адрес) → обновляются без изменения времени
- **Новые услуги** → создаются новые записи с **текущим временем редактирования**
- **Старые услуги** → время и порядок не изменяются

**⭐ ВАЖНО**: Новые услуги получают текущее время (время редактирования), но номер в очереди присваивается последним (после всех, кто уже получил очередь на эту услугу). Это справедливо, потому что пациент решил воспользоваться дополнительной услугой ПОЗЖЕ, чем другие пациенты уже получили очередь на эту услугу.

#### 4. Автоматическая блокировка QR

QR-регистрация автоматически блокируется:
- При открытии приёма (`opened_at` установлен)
- По истечении времени онлайн-регистрации (`online_end_time`)
- До начала времени онлайн-регистрации (`online_start_time`)

---

## База данных

### Новые поля в моделях

#### `OnlineQueueEntry`

```python
queue_time = Column(DateTime(timezone=True), nullable=True, index=True)
source = Column(String(20), nullable=False)  # 'online', 'desk', 'morning_assignment'
```
- **Назначение**: Бизнес-время регистрации (отдельно от `created_at`)
- **Использование**: Определяет приоритет в очереди
- **Особенности**:
  - Не изменяется при редактировании
  - Индексируется для быстрого поиска
  - Может быть `NULL` для старых записей (backfilled из `created_at`)

- **source**: Источник регистрации
  - `'online'` - QR-регистрация
  - `'desk'` - Ручная регистрация в регистратуре
  - `'morning_assignment'` - Автоматическое присвоение номеров утренней сборкой

#### `QueueToken`

```python
specialist_id = Column(Integer, ForeignKey('doctors.id'), nullable=True)
is_clinic_wide = Column(Boolean, default=False, nullable=False)
```

- **`specialist_id`**: Теперь может быть `NULL` для общего QR клиники
- **`is_clinic_wide`**: Флаг общего QR-кода (без привязки к специалисту)

### Структура данных

#### Основные таблицы

1. **`daily_queues`** - Дневные очереди по специалистам
   - `day` - Дата очереди
   - `specialist_id` - ID специалиста
   - `opened_at` - Время открытия приёма
   - `online_start_time` - Начало онлайн-регистрации (по умолчанию 07:00)
   - `online_end_time` - Конец онлайн-регистрации (по умолчанию 09:00)
   - `max_online_entries` - Максимум онлайн-записей

2. **`queue_entries`** - Записи в очереди
   - `queue_id` - Ссылка на дневную очередь
   - `patient_id` - ID пациента (опционально)
   - `number` - Номер в очереди
   - `queue_time` - ⭐ **НОВОЕ**: Время регистрации
   - `source` - ⭐ **ОБНОВЛЕНО**: Источник: `'online'`, `'desk'`, или `'morning_assignment'`
   - `status` - Статус: `'waiting'`, `'called'`, `'completed'`, `'cancelled'`

3. **`queue_tokens`** - QR-токены
   - `token` - Уникальный токен
   - `day` - Дата очереди
   - `specialist_id` - ⭐ **ИЗМЕНЕНО**: Может быть `NULL`
   - `is_clinic_wide` - ⭐ **НОВОЕ**: Флаг общего QR
   - `expires_at` - Время истечения
   - `active` - Активен ли токен

---

## API Endpoints

### Публичные endpoints (без авторизации)

#### 1. `GET /api/v1/queue/available-specialists`

**Назначение**: Получить список доступных специалистов для QR-регистрации

**Ответ**:
```json
{
  "success": true,
  "specialists": [
    {
      "id": 1,
      "specialty": "cardiology",
      "specialty_display": "Кардиолог",
      "icon": "❤️",
      "color": "#FF3B30",
      "doctor_name": "Иванов Иван Иванович",
      "cabinet": "101"
    }
  ],
  "total": 4
}
```

#### 2. `GET /api/v1/queue/qr-tokens/{token}/info`

**Назначение**: Получить информацию о QR-токене

**Ответ**:
```json
{
  "token": "abc123...",
  "specialist_id": null,
  "specialist_name": "Клиника",
  "department": "general",
  "queue_active": true,
  "is_clinic_wide": true
}
```

#### 3. `POST /api/v1/queue/join/start`

**Назначение**: Начать сессию присоединения к очереди

**Запрос**:
```json
{
  "token": "abc123..."
}
```

**Ответ**:
```json
{
  "session_token": "session_xyz...",
  "expires_at": "2025-01-15T10:00:00Z",
  "queue_info": {
    "is_clinic_wide": true,
    "specialists_available": [...]
  }
}
```

#### 4. `POST /api/v1/queue/join/complete`

**Назначение**: Завершить регистрацию в очереди

**Запрос** (одиночная регистрация):
```json
{
  "session_token": "session_xyz...",
  "patient_name": "Иванов Иван",
  "phone": "+998901234567"
}
```

**Запрос** (множественная регистрация):
```json
{
  "session_token": "session_xyz...",
  "patient_name": "Иванов Иван",
  "phone": "+998901234567",
  "specialist_ids": [1, 2, 4]
}
```

**Ответ** (множественная):
```json
{
  "success": true,
  "queue_time": "2025-01-15T07:30:00+05:00",
  "entries": [
    {
      "specialist_id": 1,
      "specialist_name": "Иванов И.И.",
      "department": "cardiology",
      "number": 3,
      "queue_id": 15,
      "queue_time": "2025-01-15T07:30:00+05:00",
      "icon": "❤️"
    }
  ],
  "message": "Вы записаны к 3 специалистам"
}
```

### Административные endpoints (требуют авторизации)

#### 5. `POST /api/v1/queue/qr-tokens/admin/generate-clinic`

**Назначение**: Создать общий QR-код для клиники

**Требуемые роли**: `Admin`, `Registrar`

**Запрос**:
```json
{
  "target_date": "2025-01-15",
  "expires_hours": 24
}
```

**Ответ**:
```json
{
  "token": "clinic_qr_abc123...",
  "qr_url": "/queue/join?token=clinic_qr_abc123...",
  "qr_code_base64": "data:image/png;base64,...",
  "day": "2025-01-15",
  "is_clinic_wide": true
}
```

#### 6. `POST /api/v1/registrar-integration/queue/entries/batch`

**Назначение**: Массовое создание записей в очереди (при добавлении новых услуг)

**Требуемые роли**: `Admin`, `Registrar`

**Запрос**:
```json
{
  "patient_id": 123,
  "source": "desk",
  "services": [
    {
      "specialist_id": 2,
      "service_id": 5,
      "quantity": 1
    }
  ]
}
```

**Ответ**:
```json
{
  "success": true,
  "entries": [
    {
      "specialist_id": 2,
      "queue_id": 20,
      "number": 8,
      "queue_time": "2025-01-15T14:10:00+05:00"
    }
  ],
  "message": "Создано 1 записей в очереди"
}
```

---

## Frontend компоненты

### 1. `QueueJoin.jsx` - QR-регистрация

**Расположение**: `frontend/src/pages/QueueJoin.jsx`

**Основные функции**:
- Загрузка списка специалистов из API
- Выбор нескольких специалистов через чекбоксы
- Отправка данных для множественной регистрации
- Отображение результата (одиночная/множественная)

**Ключевые состояния**:
```javascript
const [availableSpecialists, setAvailableSpecialists] = useState([]);
const [selectedSpecialists, setSelectedSpecialists] = useState([]);
const [step, setStep] = useState('loading'); // loading | info | select-specialists | success | error
```

**Шаги процесса**:
1. `loading` - Загрузка информации о токене
2. `info` - Ввод данных пациента (для одиночного QR)
3. `select-specialists` - Выбор специалистов (для общего QR)
4. `success` - Экран успеха с результатами
5. `error` - Ошибка регистрации

**Экран успеха**:
- **Одиночная регистрация**: Показывает номер очереди, время ожидания, специалиста
- **Множественная регистрация**: Показывает список всех записей с номерами и временем

### 2. `AppointmentWizardV2.jsx` - Мастер регистрации

**Расположение**: `frontend/src/components/wizard/AppointmentWizardV2.jsx`

**Режим редактирования**:
- **Обычные визиты (desk/admin)**:
  - Определяет новые услуги путём сравнения с исходными
  - Создаёт новые записи очереди для новых услуг через batch endpoint
- **QR-записи (online)**:
  - Использует SSOT-метод `updateOnlineQueueEntry` (`PUT .../full-update`)
  - Атомарно обновляет пациента и список услуг
  - Backend сам управляет добавлением новых услуг и сохранением старых
  - **ВАЖНО**: Не создает дубликатов визитов

**Логика определения новых услуг (для desk записей)**:
```javascript
const existingServiceIds = initialData.services 
  ? initialData.services.map(s => s.service_id || s.id)
  : [];
const currentServiceIds = wizardData.cart.items.map(item => item.service_id);
const newServiceIds = currentServiceIds.filter(id => !existingServiceIds.includes(id));
```

### 3. `ModernQueueManager.jsx` - Управление очередью

**Расположение**: `frontend/src/components/queue/ModernQueueManager.jsx`

**Визуальные метки**:
- **QR (ранняя)** - для записей с `source === 'online'`
- **Manual** - для записей с `source === 'desk'`

**Кнопка "Открыть прием"**:
- Визуальные эффекты: hover, active, transitions
- Автоматическая блокировка QR после открытия

### 4. `EnhancedAppointmentsTable.jsx` - Таблица записей

**Расположение**: `frontend/src/components/tables/EnhancedAppointmentsTable.jsx`

**Метки источника**:
- Отображаются рядом с именем пациента
- Цветовая индикация для QR-записей

---

## Сценарии использования

### Сценарий 1: QR-регистрация утром (множественная)

**Время**: 07:30

**Действия**:
1. Пациент сканирует общий QR-код клиники
2. Вводит: Имя, Фамилия, Телефон
3. Выбирает: Кардиолог ✅, Лаборатория ✅
4. Нажимает "Зарегистрироваться"

**Результат**:
- Создаются 2 записи `OnlineQueueEntry`:
  - Кардиолог: номер 3, `queue_time = 2025-01-15 07:30:00`
  - Лаборатория: номер 5, `queue_time = 2025-01-15 07:30:00`
- Обе записи имеют `source = 'online'`
- Пациент видит экран успеха с обеими записями

### Сценарий 2: Открытие клиники

**Время**: 09:00

**Действия**:
1. Регистратор нажимает "Открыть прием"
2. Система устанавливает `opened_at = 2025-01-15 09:00:00`

**Результат**:
- QR-регистрация автоматически блокируется
- Все попытки QR-регистрации получают ошибку "Запись закрыта - прием уже открыт"
- Существующие QR-записи сохраняют своё время и приоритет

### Сценарий 3: Добавление услуги в регистратуре

**Время**: 14:10

**Исходная ситуация**:
- Пациент зарегистрирован через QR в 07:30 на кардиолога

**Действия**:
1. Регистратор находит пациента в таблице
2. Нажимает "Редактировать"
3. Добавляет услугу "Лаборатория"
4. Сохраняет

**Результат**:
- Личные данные пациента обновлены
- Создана новая запись `OnlineQueueEntry`:
  - Лаборатория: номер = последний в очереди (например, 12, если до этого было 11 записей)
  - `queue_time = 2025-01-15 14:10:00` (⭐ текущее время редактирования)
  - `source = 'online'` (сохраняется оригинальный источник)
- Старая запись (кардиолог) не изменена:
  - Номер 3, `queue_time = 2025-01-15 07:30:00`

**⭐ Справедливость**: Пациент получает последний номер в очереди (12), потому что он решил воспользоваться услугой позже (14:10), чем другие пациенты уже получили очередь на эту услугу (например, в 10:00, 11:00, 12:00). Он не обгонит тех, кто уже был в очереди.

### Сценарий 4: Ручная регистрация в регистратуре

**Время**: 10:00

**Действия**:
1. Пациент приходит в регистратуру
2. Регистратор создаёт запись через `AppointmentWizardV2`
3. Выбирает услуги: Дерматолог, Стоматолог

**Результат**:
- Создаются записи с `source = 'desk'`
- `queue_time = 2025-01-15 10:00:00`
- В UI отображается метка "Manual"

### Сценарий 5: Добавление услуги к ручной записи

**Время**: 11:30

**Исходная ситуация**:
- Пациент зарегистрирован вручную в 10:00 на дерматолога

**Действия**:
1. Регистратор редактирует запись
2. Добавляет услугу "Лаборатория"

**Результат**:
- Новая запись: `source = 'desk'`, `queue_time = 2025-01-15 11:30:00`
- Старая запись не изменена

### Сценарий 6: Утренняя сборка (Morning Assignment)

**Время**: 06:00 (автоматически)

**Исходная ситуация**:
- Пациент заранее записался на прием и подтвердил визит
- Статус визита: `confirmed`
- У пациента есть услуги с queue_tag: `cardiology_common`, `lab`, `ecg`

**Процесс**:
1. Система автоматически запускает `morning_assignment_service.py`
2. Находит все подтвержденные визиты на текущий день
3. Для каждого queue_tag создает запись в соответствующей очереди

**Результат**:
- Создаются записи `OnlineQueueEntry`:
  - Кардиология (queue_tag='cardiology_common'): номер 1, `source = 'morning_assignment'`
  - Лаборатория (queue_tag='lab'): номер 1, `source = 'morning_assignment'`
  - ЭКГ (queue_tag='ecg'): номер 1, `source = 'morning_assignment'`
- Статус визита меняется на `open`
- Patient_name и phone могут отсутствовать (берутся из таблицы patients по patient_id)

**Особенности**:
- Используются ресурс-врачи для очередей без конкретного специалиста
- queue_tag определяет, в какую очередь попадает пациент
- `queue_time` устанавливается в момент создания записи

---

## Технические детали

### Временные зоны

Все времена хранятся с учётом временной зоны:
```python
from zoneinfo import ZoneInfo
timezone = ZoneInfo("Asia/Tashkent")
queue_time = datetime.now(timezone)
```

### Валидация времени регистрации

Проверки в `_check_online_time_restrictions()`:
1. Токен существует и активен
2. Очередь не открыта (`opened_at == None`)
3. Текущее время >= `online_start_time` (по умолчанию 07:00)
4. Текущее время <= `online_end_time` (по умолчанию 09:00)
5. Не превышен лимит записей

### Группировка по специальностям

При загрузке специалистов из API:
- Группируются по специальности
- Выбирается первый врач из каждой группы
- Автоматически определяется иконка и цвет

### Fallback механизмы

**Frontend**:
- При ошибке загрузки специалистов → статический список
- При ошибке API → показ сообщения об ошибке

**Backend**:
- При отсутствии настроек → значения по умолчанию
- При отсутствии специалиста → использование ID

---

## Миграции БД

### Миграция `b9716387212f_add_queue_time_and_clinic_wide_qr`

**Файл**: `backend/alembic/versions/b9716387212f_add_queue_time_and_clinic_wide_qr.py`

**Изменения**:

1. **Добавление `queue_time` в `queue_entries`**:
   ```sql
   ALTER TABLE queue_entries ADD COLUMN queue_time DATETIME;
   ```

2. **Backfill данных**:
   ```sql
   UPDATE queue_entries SET queue_time = created_at WHERE queue_time IS NULL;
   ```

3. **Создание индекса**:
   ```sql
   CREATE INDEX idx_queue_entries_queue_time ON queue_entries(queue_time);
   ```

4. **Изменение `specialist_id` в `queue_tokens`**:
   ```sql
   -- SQLite workaround: пересоздание таблицы
   ALTER TABLE queue_tokens ADD COLUMN specialist_id_new INTEGER;
   UPDATE queue_tokens SET specialist_id_new = specialist_id;
   -- ... (полная миграция в файле)
   ```

5. **Добавление `is_clinic_wide`**:
   ```sql
   ALTER TABLE queue_tokens ADD COLUMN is_clinic_wide BOOLEAN DEFAULT 0;
   ```

**Применение**:
```bash
cd backend
python -m alembic upgrade b9716387212f
```

---

## Файлы изменений

### Backend

1. **Модели**:
   - `backend/app/models/online_queue.py` - добавлены поля `queue_time`, `is_clinic_wide`

2. **Сервис очередей (SSOT)**:
   - `backend/app/services/queue_service.py` — ключевые функции `assign_queue_token()`, `create_queue_entry()`, `get_next_queue_number()`

3. **API Endpoints**:
   - `backend/app/api/v1/endpoints/qr_queue.py` - endpoint `/available-specialists`
   - `backend/app/api/v1/endpoints/registrar_integration.py` - endpoint `/queue/entries/batch`
   - `backend/app/api/v1/endpoints/queue.py` - обновлён `create_queue_entry()`
   - `backend/app/api/v1/endpoints/visit_confirmation.py` - обновлён `create_queue_entry_for_visit()`

4. **Сервисы**:
   - `backend/app/services/qr_queue_service.py` - обновлена логика проверок
   - `backend/app/services/morning_assignment.py` - ⭐ **ИСПРАВЛЕНО**: использует doctor_id вместо user_id для ресурс-врачей

5. **Миграции**:
   - `backend/alembic/versions/b9716387212f_add_queue_time_and_clinic_wide_qr.py`

### Frontend

1. **Страницы**:
   - `frontend/src/pages/QueueJoin.jsx` - динамическая загрузка специалистов, экран успеха

2. **Компоненты**:
   - `frontend/src/components/wizard/AppointmentWizardV2.jsx` - гибридное редактирование
   - `frontend/src/components/queue/ModernQueueManager.jsx` - метки источника, эффекты кнопки
   - `frontend/src/components/tables/EnhancedAppointmentsTable.jsx` - метки источника
   - `frontend/src/pages/RegistrarPanel.jsx` - ⭐ **ДОБАВЛЕНО**: маппинг queue_tag → вкладки. **Дедупликация**: Online Queue разделяется по специальностям (`online_phone_date_specialty`), чтобы обеспечить корректное время в табах отделений. Вкладка "Все отделения" использует агрегацию `aggregatePatientsForAllDepartments`.

---

## Тестирование

### Рекомендуемые тестовые сценарии

1. **QR-регистрация**:
   - Одиночная регистрация
   - Множественная регистрация (2-4 специалиста)
   - Регистрация до открытия (07:00-09:00)
   - Попытка регистрации после открытия (должна быть заблокирована)

2. **Редактирование**:
   - Обновление личных данных (не должно менять время)
   - Добавление новой услуги (должна создать новую запись)
   - Добавление нескольких услуг одновременно

3. **Отображение**:
   - Метки источника отображаются корректно
   - Время регистрации показывается правильно
   - Номера очередей корректны

4. **Граничные случаи**:
   - Пациент уже записан в очередь (дубликат)
   - Очередь заполнена (лимит)
   - Токен истёк
   - Очередь уже открыта

---

## Известные ограничения

1. **Статический список специалистов**: При ошибке загрузки используется fallback (планируется улучшение)
2. **Ручное изменение приоритета**: Не реализовано (низкий приоритет)
3. **История изменений**: Не ведётся детальный audit log для изменений `queue_time`

---

## Будущие улучшения

1. ✅ Динамический список специалистов (реализовано)
2. ✅ Экран успеха для множественной регистрации (реализовано)
3. ⏸️ Ручное изменение приоритета с логом (низкий приоритет)
4. ⏸️ SMS-уведомления о регистрации
5. ⏸️ Печать талонов с QR-кодом
6. ⏸️ Статистика по источникам регистрации

---

## Контакты и поддержка

При возникновении вопросов или проблем:
1. Проверьте логи backend: `backend/app/logs/`
2. Проверьте консоль браузера для frontend ошибок
3. Убедитесь, что миграции применены: `python -m alembic current`

---

**Дата создания документа**: 2025-01-15  
**Версия системы**: 1.0.0  
**Статус**: ✅ Реализовано и протестировано

---

## Интеграция `AppointmentWizardV2` с онлайн-очередями (чек‑лист)

### Backend (очереди и визиты)

- [x] **SSOT-модели очередей**  
  Используются только `DailyQueue`, `OnlineQueueEntry`, `QueueToken` (`app/models/online_queue.py`). Поля `queue_time`, `source`, `is_clinic_wide` применяются согласно разделу «База данных».

- [x] **QR-регистрация (Scenario 1/2)**  
  `POST /api/v1/queue/join/start` и `POST /api/v1/queue/join/complete` (в т.ч. множественная) создают **только** `queue_entries` c `source='online'` и корректным `queue_time`. В этот момент визиты не создаются. Реализация: `QRQueueService.join_queue_with_token()` / `complete_join_session(_multiple)` + `QueueBusinessService.create_queue_entry()`.

- [x] **Ручной сценарий через мастер (desk, Scenario 4/5)**  
  Endpoint: `POST /api/v1/registrar/cart` (`create_cart_appointments` в `app/api/v1/endpoints/registrar_wizard.py`).  
  Вход строго соответствует `CartRequest` (`patient_id`, `visits[]`, `discount_mode`, `payment_method`, `all_free`, `notes`).  
  Визиты создаются через SSOT (`create_visit` + `BillingService.calculate_total`).  
  Для визитов на сегодня номера в очереди присваиваются через `MorningAssignmentService._assign_queues_for_visit(..., source="desk")`, что даёт `OnlineQueueEntry.source='desk'` и `queue_time = текущее локальное время`.

- [x] **Утренняя сборка (Scenario 6)**  
  Сервис: `MorningAssignmentService` (`app/services/morning_assignment.py`).  
  Использует `doctor_id` (через `Doctor.user_id`) для `DailyQueue.specialist_id`.  
  Для подтверждённых визитов на текущий день создаёт `OnlineQueueEntry` с `source='morning_assignment'` и `queue_time = время запуска сборки`.

- [x] **Добавление услуг по QR (Scenario 3)**  
  Endpoint: `PUT /api/v1/queue/online-entry/{entry_id}/full-update` (`full_update_online_entry` в `qr_queue.py`).  
  Личные данные пациента обновляются без изменения `queue_time` и `number` существующих записей.  
  Новые услуги создают новые `OnlineQueueEntry` с `queue_time = текущее время редактирования`, `source='online'`, по нужному `queue_tag`.

- [x] **Batch API для очередей**  
  Endpoint: `POST /api/v1/registrar-integration/queue/entries/batch`.  
  Использует `QueueBusinessService.create_queue_entry()` (SSOT): `queue_time` устанавливается один раз, `source` берётся из запроса (`online`, `desk`, `morning_assignment`).  
  Покрыт интеграционными тестами: `backend/tests/integration/test_queue_batch_api.py`.

### Frontend (мастер и панели)

- [x] **QR‑регистрация без мастера** (`QueueJoin.jsx`)  
  Ступени интерфейса: `loading → waiting → info → select-specialists → form → success`.  
  Работает поверх публичных эндпоинтов очереди. При успешной записи шлёт `CustomEvent('queueUpdated', { detail: { action: 'refreshAll', specialty, departmentKey, entry } })` и сохраняет `lastQueueJoin` в `localStorage` для fallback-обновлений.

- [x] **Панель очередей регистратуры** (`ModernQueueManager.jsx`)  
  Использует `GET /api/v1/registrar/queues/today` как объединённый источник (`visits + appointments + queue_entries`), генерацию QR и слушает события `queueUpdated` для мгновенного обновления таблиц.

- [x] **Таблица записей** (`EnhancedAppointmentsTable.jsx`)  
  Отображает:
  - `queue_numbers[]` (номер и очередь/вкладка),
  - `source` (`online`, `desk`, `morning_assignment`, `confirmation`) с метками **QR/Manual**,
  - `discount_mode`, `payment_status`, AllFree и др.  
  
  Использует единый маппинг услуг (`service_code`/`category_code`) для кодов (K**, D**, S**, L** и т.п.) и тултипов с полными названиями.
  
  **⚠️ ВАЖНО (см. раздел 8.9 в ONLINE_QUEUE_SYSTEM_V2.md):**  
  Вкладка "Все отделения" **обязана** вызывать `filterServicesByDepartment(patient, null)` для корректного отображения всех услуг мульти-QR записей. Напрямую использовать `appointment.services` для QR-записей **ЗАПРЕЩЕНО**.
  
  **Отмена записей (aggregated_ids):**
  - `loadAppointments` собирает `aggregated_ids` при первой дедупликации (по `dedupKey`)
  - `mergeAppointments` объединяет `aggregated_ids` при второй дедупликации
  - `aggregatePatientsForAllDepartments` агрегирует все `aggregated_ids` для вкладки "Все отделения"
  - `onCancel` итерирует по `aggregated_ids` и вызывает API отмены для каждого ID
  
  Частичная отмена доступна только через редактирование в `AppointmentWizardV2`.

- [x] **`AppointmentWizardV2`** (`frontend/src/components/wizard/AppointmentWizardV2.jsx`)  
  - Новый визит (desk) → формирует `CartRequest` и вызывает `/registrar/cart`.  
  - Edit визита → восстанавливает корзину из `initialData`, отслеживает новые услуги, создаёт для них новые визиты/очереди.  
  - Edit QR‑записи → поднимает данные пациента из очереди/пациента, маппит `queue_numbers` → услуги, при завершении:
    - вызывает `updateOnlineQueueEntry` (`PUT /full-update`),
    - Backend обновляет `OnlineQueueEntry` (пациент, услуги), сохраняя `queue_time` для старых и создавая новые записи для новых услуг,
    - **CRITICAL**: Предотвращает дублирование визитов (не вызывает `create_cart`).

### Мини‑чек‑лист для ручной проверки

- [ ] **Scenario 1/2 (QR только создаёт очередь)**  
  Выполнить `queue/join/complete` (одиночный и множественный варианты) и убедиться, что создаются только `queue_entries` (`source='online'`), без новых `visits/appointments`.

- [ ] **Scenario 3 (добавление услуг по QR)**  
  Открыть QR-запись в `AppointmentWizardV2`, добавить услуги, завершить:
  - старые `queue_entries` не меняют `queue_time` и `number`,
  - для новых услуг появляются новые строки очереди с `queue_time = время редактирования`, `source='online'`.

- [ ] **Scenario 4/5 (desk)**  
  Создать визит через мастер на сегодня:
  - визиты создаются через `/registrar/cart`,
  - в очередях появляются новые записи с `source='desk'` и корректным `queue_time`.

- [ ] **Scenario 6 (morning_assignment)**  
  Подготовить подтверждённые визиты на завтра, запустить `MorningAssignmentService`:
  - создаются `OnlineQueueEntry` с `source='morning_assignment'`,
  - `DailyQueue.specialist_id` указывает на `users.id` врача.

- [ ] **Регрессия по мастеру**  
  - Новый визит (desk) по основным отделениям (кардио, дерма, стоматология, лаборатория).  
  - Edit визита с добавлением/удалением услуг.  
  - Edit QR‑записи с добавлением услуг в разные отделения (проверить, что новые очереди создаются отдельно, а старые не меняются).

---

## 📜 История изменений

### Декабрь 2024 — Рефакторинг архитектуры

#### 1. SSOT для Service Code Mappings

**Проблема:** Дублирование маппингов `codeToName`, `idToName`, `specialtyToCode` в 5+ файлах.

**Решение:** Создан централизованный модуль `frontend/src/utils/serviceCodeResolver.js`:

```javascript
// Экспортирует:
export const SPECIALTY_TO_CODE = { ... };
export const CODE_TO_NAME = { ... };
export const LEGACY_CODE_TO_NAME = { ... };
export const ID_TO_NAME = { ... };

export function toServiceCode(value) { ... }
export function getServiceDisplayName(code) { ... }
export function normalizeServicesFromInitialData(initialData) { ... }
```

**Миграция:**
- `RegistrarPanel.jsx` → импортирует из SSOT
- `EnhancedAppointmentsTable.jsx` → импортирует из SSOT
- `AppointmentWizardV2.jsx` → использует `normalizeServicesFromInitialData()`

#### 2. Batch API для записей пациента

**Проблема:** UI Row ↔ API Entry mismatch — одна строка таблицы = несколько API records.

**Решение:** Новый batch API:

```
GET    /api/v1/registrar/batch/patients/{patient_id}/entries/{date}
PATCH  /api/v1/registrar/batch/patients/{patient_id}/entries/{date}
DELETE /api/v1/registrar/batch/patients/{patient_id}/entries/{date}
```

**Файлы:**
- `backend/app/services/batch_patient_service.py`
- `backend/app/api/v1/endpoints/registrar_batch.py`
- `frontend/src/api/registrarBatch.js`

**Документация:** `docs/BATCH_UPDATE_ARCHITECTURE.md`

#### 3. Исправление расчёта длины очереди

**Проблема:** `qr_queue_service.py` смешивал `Visit` + `Appointment` + `OnlineQueueEntry`.

**Решение:** Методы `_get_queue_length()` и `get_qr_token_info()` теперь используют только `OnlineQueueEntry` для консистентности с `queue_position_notifications.py`.

#### 4. Исправление агрегации пациентов

**Проблема:** В `RegistrarPanel.jsx` функция `aggregatePatientsForAllDepartments` дедуплицировала по specialty вместо ID.

**Решение:** Дедупликация по уникальному `entry.id` — все queue entries теперь сохраняются.

#### 5. Visit Confirmation Audit

**Проблема:** PWA endpoint не извлекал `source_ip`/`user_agent` из Request.

**Решение:** Добавлен параметр `Request` и полная интеграция с `ConfirmationSecurityService`.

#### 6. Исправление отображения кодов услуг (2024-12-18)

**Проблема:** В таблице отображались fallback-коды K01/L01 вместо реальных K11/L02 из API.

**Причина:** Функция `filterServicesByDepartment()` генерировала коды из `specialty` вместо использования `appointment.services`.

**Решение:**
1. `filterServicesByDepartment()` теперь использует `appointment.services` напрямую
2. `isInDepartment()` — ECG (K10) отделён от Cardiology (K01, K11)
3. Добавлены коды: D_PROC для процедур, S10 для стоматологии

**Маппинг вкладок:**
| Вкладка | Коды |
|---------|------|
| Кардиолог | K (кроме K10) |
| ЭКГ | K10, ECG* |
| Дерматолог | D |
| Стоматолог | S |
| Лаборатория | L |
| Процедуры | P, C, D_PROC |

---

*Последнее обновление: 2025-12-19*
