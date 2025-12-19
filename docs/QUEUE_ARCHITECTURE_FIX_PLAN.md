# План исправления архитектуры очередей

## ✅ СТАТУС: КРИТИЧЕСКИЕ ФИКСЫ РЕАЛИЗОВАНЫ (2025-12-19)

### Реализованные фиксы:
- ✅ **Fix 1**: Создавать `patient_id` при QR-регистрации (`_find_or_create_patient`)
- ✅ **Fix 3**: Backend вычисляет `aggregated_ids` сам (не зависит от frontend)
- ✅ **Fix 4**: Запретить создание entries без услуг (предотвращает Entry #498)
- ✅ **Fix 5 (queue_time)**: Первое заполнение QR-записи сохраняет оригинальное время регистрации

### TODO Backend:
- ✅ **Fix 2**: Создавать `Visit` при первом заполнении QR-записи (реализовано 2025-12-19)
- ⏳ **Fix 5 (filter)**: Silent ignore пустых entries в выборке (низкий приоритет)

### TODO Frontend (баги в отображении):
- 🐛 **Frontend Bug 1**: Код услуги `О01` отображается вместо реальных кодов (K01, K10, L10)
- 🐛 **Frontend Bug 2**: Новая лабораторная услуга показывает `queue_time = 17:07:47` вместо реального времени добавления (`17:28:12`)
  - В БД данные корректные (Entry #505 имеет `queue_time=12:28:12 UTC = 17:28 local`)
  - Проблема в frontend агрегации/отображении



## 📋 Диагноз проблемы

### Корневая причина
QR-регистрация создаёт `OnlineQueueEntry` **без** `patient_id` и `visit_id`. 
Из-за этого при редактировании backend не может определить существующие услуги пациента.

### Симптомы
1. `Entry #498` с пустыми услугами (`services: []`)
2. Дублирование entries при редактировании
3. `aggregated_ids` приходит с frontend (ненадёжно)
4. `queue_time` перезаписывается для существующих услуг

---

## 🎯 Минимальный набор фиксов

### Fix 1: Создавать `patient_id` при QR-регистрации

**Файл**: `backend/app/services/qr_queue_service.py`

**Изменение в `complete_join_session` и `complete_join_session_multiple`**:

```python
# БЫЛО:
patient = self.db.query(Patient).filter(Patient.phone == phone).first()
# patient_id = patient.id if patient else None  ← НЕ создаёт нового!

# СТАНЕТ:
patient = self._find_or_create_patient(patient_name, phone)
# patient_id = patient.id  ← ВСЕГДА есть!
```

**Новый метод**:
```python
def _find_or_create_patient(
    self, 
    patient_name: str, 
    phone: str,
    birth_year: Optional[int] = None,
    address: Optional[str] = None
) -> Patient:
    """
    Находит или создаёт пациента по телефону.
    SSOT для создания пациентов при QR-регистрации.
    """
    # Нормализуем телефон
    clean_phone = re.sub(r'\D', '', phone)
    
    # Ищем по телефону
    patient = self.db.query(Patient).filter(
        func.replace(func.replace(Patient.phone, '+', ''), ' ', '') == clean_phone
    ).first()
    
    if patient:
        return patient
    
    # Создаём нового пациента
    from app.crud.patient import normalize_patient_name
    name_parts = normalize_patient_name(full_name=patient_name)
    
    patient = Patient(
        last_name=name_parts.get("last_name") or "Неизвестный",
        first_name=name_parts.get("first_name") or "Пациент",
        middle_name=name_parts.get("middle_name"),
        phone=phone,
        birth_date=date(birth_year, 1, 1) if birth_year else None,
        address=address,
    )
    self.db.add(patient)
    self.db.flush()
    
    logger.info(
        "[QRQueueService] Создан новый пациент ID=%d для QR-регистрации: %s, %s",
        patient.id, patient_name, phone
    )
    
    return patient
```

---

### Fix 2: Создавать `Visit` при QR-регистрации

**Файл**: `backend/app/services/qr_queue_service.py`

**Новый метод**:
```python
def _create_visit_for_qr(
    self,
    patient_id: int,
    visit_date: date,
    services: List[Dict[str, Any]],
    source: str = "online"
) -> Visit:
    """
    Создаёт Visit для QR-регистрации.
    Visit создаётся сразу, даже если нет оплаты.
    """
    from app.models.visit import Visit, VisitService
    
    visit = Visit(
        patient_id=patient_id,
        visit_date=visit_date,
        status="open",
        discount_mode="none",
        approval_status="none",
        notes=f"QR-регистрация ({source})",
    )
    self.db.add(visit)
    self.db.flush()
    
    # Добавляем услуги
    for svc_data in services:
        visit_service = VisitService(
            visit_id=visit.id,
            service_id=svc_data["service_id"],
            code=svc_data.get("code"),
            name=svc_data.get("name", "Услуга"),
            qty=svc_data.get("quantity", 1),
            price=svc_data.get("price"),
        )
        self.db.add(visit_service)
    
    self.db.flush()
    
    logger.info(
        "[QRQueueService] Создан Visit ID=%d для QR-пациента %d с %d услугами",
        visit.id, patient_id, len(services)
    )
    
    return visit
```

---

### Fix 3: Backend вычисляет `aggregated_ids` сам

**Файл**: `backend/app/api/v1/endpoints/qr_queue.py`

**Изменение в `full_update_online_entry`** (строки ~1239-1270):

```python
# БЫЛО:
if request.aggregated_ids and len(request.aggregated_ids) > 0:
    all_entries = db.query(OnlineQueueEntry).filter(
        OnlineQueueEntry.id.in_(request.aggregated_ids)
    ).all()

# СТАНЕТ:
# ⭐ Backend САМ вычисляет aggregated_ids по patient_id + дате
aggregated_ids = []

if entry.patient_id:
    # Находим все entries этого пациента за сегодня
    today = date.today()
    patient_entries = (
        db.query(OnlineQueueEntry)
        .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
        .filter(
            OnlineQueueEntry.patient_id == entry.patient_id,
            DailyQueue.day == today,
            OnlineQueueEntry.status.in_(["waiting", "called", "in_service"]),
        )
        .all()
    )
    aggregated_ids = [e.id for e in patient_entries]
elif entry.phone:
    # Fallback: по телефону
    today = date.today()
    phone_entries = (
        db.query(OnlineQueueEntry)
        .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
        .filter(
            OnlineQueueEntry.phone == entry.phone,
            DailyQueue.day == today,
            OnlineQueueEntry.status.in_(["waiting", "called", "in_service"]),
        )
        .all()
    )
    aggregated_ids = [e.id for e in phone_entries]

# Frontend aggregated_ids используем только как fallback
if not aggregated_ids and request.aggregated_ids:
    aggregated_ids = request.aggregated_ids
    logger.warning(
        "[full_update_online_entry] ⚠️ Используем aggregated_ids из frontend (fallback): %s",
        aggregated_ids
    )

logger.info(
    "[full_update_online_entry] ⭐ Вычисленные aggregated_ids: %s",
    aggregated_ids
)

all_entries = db.query(OnlineQueueEntry).filter(
    OnlineQueueEntry.id.in_(aggregated_ids)
).all() if aggregated_ids else [entry]
```

---

### Fix 4: Запретить создание entries без услуг

**Файл**: `backend/app/services/queue_service.py`

**Изменение в `create_queue_entry`** (после строки 910):

```python
# НОВОЕ: Валидация — entry без услуг не создаётся
if services is None or (isinstance(services, list) and len(services) == 0):
    logger.warning(
        "[create_queue_entry] ⚠️ Попытка создать entry без услуг для patient_id=%s, phone=%s",
        patient_id, phone
    )
    # Для QR-регистрации без услуг — это ошибка
    if source == "online":
        raise QueueValidationError("Необходимо выбрать хотя бы одну услугу")
```

**Изменение в `full_update_online_entry`** (перед созданием new_queue_entry):

```python
# НОВОЕ: Не создаём entry если services_list_new пустой
if not services_list_new:
    logger.warning(
        "[full_update_online_entry] ⚠️ Пропуск создания entry для %s — нет услуг",
        queue_tag
    )
    continue
```

---

### Fix 5: Silent ignore пустых entries в выборке

**Файл**: `backend/app/api/v1/endpoints/registrar_integration.py`

**Изменение в `get_today_queues`**:

```python
# Фильтруем пустые entries
entries = [
    e for e in all_entries 
    if e.services and len(json.loads(e.services) if isinstance(e.services, str) else e.services) > 0
]

logger.info(
    "[get_today_queues] Отфильтровано %d пустых entries",
    len(all_entries) - len(entries)
)
```

---

## 📊 Порядок применения фиксов

1. **Fix 4** — Запретить создание entries без услуг (предотвращает новые баги)
2. **Fix 5** — Silent ignore пустых entries (чистим UI от мусора)
3. **Fix 1** — Создавать patient_id при QR (критичный)
4. **Fix 2** — Создавать Visit при QR (критичный)
5. **Fix 3** — Backend вычисляет aggregated_ids (убирает зависимость от frontend)

---

## 🧪 Тестовые сценарии

### Сценарий A: Новая QR-регистрация
1. Пациент сканирует QR
2. Выбирает: Кардиолог + ЭКГ
3. **Ожидаемый результат**:
   - Создан `Patient` (если не существовал)
   - Создан `Visit` с 2 `VisitService`
   - Созданы 2 `OnlineQueueEntry` с `patient_id` и `visit_id`

### Сценарий B: Редактирование QR-записи
1. Регистратор открывает запись пациента
2. Добавляет услугу "Анализ крови"
3. **Ожидаемый результат**:
   - Старые entries сохраняют `queue_time`
   - Создан новый `OnlineQueueEntry` для анализа крови с `queue_time = now()`
   - `aggregated_ids` вычислен backend'ом по `patient_id`

### Сценарий C: Проверка защиты от пустых entries
1. Попытка создать `OnlineQueueEntry` без услуг
2. **Ожидаемый результат**: Ошибка валидации

---

## 📈 Метрики успеха

- [ ] 0 новых entries с `services: []`
- [ ] 100% QR-записей имеют `patient_id`
- [ ] 100% QR-записей имеют `visit_id`
- [ ] `aggregated_ids` не используется из frontend
- [ ] Нет дублирования entries при редактировании

---

## 📅 Создано
**Дата**: 2025-12-19
**Автор**: Antigravity + Claude
