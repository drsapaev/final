# SSOT Migration: Queue Architecture Fix

## ⚠️ Корневая проблема
Visit и OnlineQueueEntry смешаны. Очередь вычисляется из двух источников → цепные баги.

## ✅ Исправлено
- [x] Frontend вызывает full-update endpoint (не cart) для QR-записей
- [x] API возвращает OnlineQueueEntry.id (не Visit.id) для QR-визитов  
- [x] queue_time сохраняется при редактировании БЕЗ изменения услуг

## ❌ Новые проблемы (следствия патчевого подхода)
- [ ] **P1**: Новая услуга не получает новое queue_time и номер
- [ ] **P2**: Статус меняется на "запланирован" вместо "В очереди"
- [ ] **P3**: Стоимость не отображается
- [ ] **P4**: Вкладка ЭКГ показывает услуги D01 (неверная фильтрация)

---

## 🎯 Правильное решение: Архитектурный рефакторинг

### Принцип 1: Visit ≠ Queue
```
Visit = контейнер платежей, содержит VisitService
OnlineQueueEntry = запись в очереди с queue_time, number, source
```

### Принцип 2: Очередь управляется ТОЛЬКО через OnlineQueueEntry
- Visit НЕ влияет на порядок
- queue_time и number живут ТОЛЬКО в OnlineQueueEntry
- source живёт в OnlineQueueEntry (уже есть)

### Принцип 3: Добавление услуг → новая OnlineQueueEntry
```
Редактирование данных пациента → НЕТ новой entry, сохраняем queue_time
Добавление услуги → НОВАЯ entry с новым queue_time и number
```

### Принцип 4: Статус и сумма вычисляются из entries
```python
status = compute_from_entries(all_patient_entries_today)
payment_sum = sum(entry.total_amount for entry in entries)
```

---

## Этапы рефакторинга

### Phase 1: Разорвать Visit → Queue
- [ ] get_today_queues: очередь ТОЛЬКО из OnlineQueueEntry
- [ ] Visit не определяет record_type="online_queue"
- [ ] Убрать entry_type_for_visit логику

### Phase 2: Изменить логику full_update
- [ ] Редактирование данных → update existing entry, preserve queue_time
- [ ] Добавление услуги → create NEW entry с текущим queue_time и новым number
- [ ] Удаление услуги → soft-delete entry (status='cancelled')

### Phase 3: Единый источник статуса и суммы
- [ ] status вычисляется из entries, не из Visit
- [ ] total_cost вычисляется из entries.services, не из VisitService

### Phase 4: Фильтрация по вкладкам
- [ ] Фильтрация по specialty из entry, не из Visit

---

## Status: ARCHITECTURAL REFACTORING REQUIRED
Патчевый подход исчерпан. Нужен systematic fix.
