---
description: SSOT Architecture Rules - ОБЯЗАТЕЛЬНЫЕ правила для всех изменений в коде
---

# 🏗️ SSOT Architecture Rules

**ВНИМАНИЕ: Эти правила ОБЯЗАТЕЛЬНЫ для выполнения при любых изменениях в коде!**

---

## Принцип: Backend — единственный источник истины

### Frontend НИКОГДА НЕ:

1. **❌ Угадывает** — не выводит данные, которые должен предоставить backend
   ```javascript
   // ❌ ЗАПРЕЩЕНО
   if (serviceName.includes('кардио')) dept = 'cardio';
   
   // ✅ ПРАВИЛЬНО
   const dept = appointment.department_key; // Используем backend поле
   ```

2. **❌ Агрегирует бизнес-сущности** — не объединяет/дедуплицирует domain объекты
   ```javascript
   // ❌ ЗАПРЕЩЕНО
   const mergedByPatientKey = new Map();
   appointments.forEach(a => mergedByPatientKey.set(key, merge(a, existing)));
   
   // ✅ ПРАВИЛЬНО
   const entries = data.flatMap(q => q.entries.map(adaptEntry)); // 1:1 mapping
   ```

3. **❌ Компенсирует кривые данные** — не исправляет несоответствия на клиенте
   ```javascript
   // ❌ ЗАПРЕЩЕНО
   const dept = queue_tag || specialty || department_key || 'unknown';
   
   // ✅ ПРАВИЛЬНО
   const dept = appointment.department_key; // Backend ОБЯЗАН предоставить
   ```

4. **❌ Содержит domain-логику** — не реализует бизнес-правила
   ```javascript
   // ❌ ЗАПРЕЩЕНО (465 строк heuristics)
   if (queue_numbers.some(qn => specialtyMapping[qn.queue_tag] === dept)) return true;
   
   // ✅ ПРАВИЛЬНО (11 строк)
   return appointment.queue_tag === dept || appointment.department_key === dept;
   ```

---

## Frontend МОЖЕТ содержать:

### 1. Presentation Logic (форматирование, сортировка, визуальная группировка)
```javascript
// ✅ РАЗРЕШЕНО
const formatQueueNumber = (num) => `№${num}`;
const sortByTime = (a, b) => new Date(a.queue_time) - new Date(b.queue_time);
const groupedByPatient = useMemo(() => { /* visual grouping only */ }, []);
```

### 2. Temporary Adapters (с ОБЯЗАТЕЛЬНОЙ пометкой)
```javascript
// ✅ РАЗРЕШЕНО с пометкой
// ⚠️ TEMPORARY ADAPTER: Remove when backend provides queue_numbers directly
// Ticket: BACKEND-1234
const adaptEntry = (entry) => ({
  ...entry,
  queue_numbers: entry.queue_numbers || [],
});
```

---

## Чек-лист при code review:

- [ ] Нет `if (field.includes('...'))` для определения domain логики
- [ ] Нет `Map()` для дедупликации бизнес-сущностей
- [ ] Нет fallback цепочек `a || b || c || 'default'` для domain полей
- [ ] Нет `specialtyToDepartmentMapping` или подобных словарей
- [ ] Все временные адаптеры помечены `// ⚠️ TEMPORARY ADAPTER`
- [ ] Сортировка/группировка — только для presentation

---

## 🚫 ЗАПРЕЩЕНО НАВСЕГДА (FOREVER BANNED)

Если найдено в коде — **STOP and ask for backend change**:

| Паттерн | Почему запрещён |
|---------|-----------------|
| `queue_numbers.some(...)` | Domain логика membership |
| `mergeAppointments` | Бизнес-дедупликация |
| `calcPriority` | Domain приоритизация |
| `logger.warn` про "вкладки/фильтры/excluded" | Шумные логи нормальной работы |
| `specialtyToDepartmentMapping` | Клиентский маппинг |
| `if (name.includes('...')) department = ...` | Эвристика department |
| `appointmentsMap = new Map()` | Дедупликация domain объектов |

### Действие при обнаружении:
1. ❌ НЕ чинить на фронтенде
2. ✅ Создать тикет для backend
3. ✅ Спросить пользователя как действовать

---

## 📋 Мини-чек перед каждым PR:

- [ ] Есть ли новый filter по department? → **PR запрещён**
- [ ] Есть ли новая агрегация вне presentation? → **PR запрещён**  
- [ ] Есть ли новые mapping-словари? → **PR запрещён**

---

## 🎯 QueueProfile Rules (Phase 2)

**QueueProfile** — единственный источник конфигурации вкладок очередей.

### Правила:

1. **❌ Frontend НЕ хардкодит вкладки** — вкладки загружаются из API `/queues/profiles`
2. **✅ Новые вкладки добавляются ТОЛЬКО через QueueProfile** — в БД или миграции
3. **✅ Service.queue_tag — основной ключ маршрутизации** — определяет в какую очередь попадает услуга
4. **✅ QueueProfile.queue_tags — массив допустимых тегов** — определяет какие queue_tag показывать на вкладке

### Маршрутизация записей:

```javascript
// ✅ ПРАВИЛЬНО: Фильтрация по queue_tags из профиля
const profileEntries = entries.filter(e => 
  currentProfile.queue_tags.includes(e.queue_tag)
);

// ❌ ЗАПРЕЩЕНО: Хардкод тегов в коде
const cardioEntries = entries.filter(e => 
  ['cardio', 'cardiology'].includes(e.queue_tag)  // Это ЗАПРЕЩЕНО
);
```

---

## 🔗 Session ID Rules (Phase 1)

**session_id** — opaque строка для группировки услуг одного пациента в очереди.

### Правила:

1. **❌ Frontend НЕ парсит session_id** — формат определяется только backend
2. **✅ Группировка по session_id — ТОЛЬКО для presentation** — объединение визуальное
3. **✅ Каждая OnlineQueueEntry имеет session_id** — заполняется при создании записи
4. **✅ Один patient + один queue + один day = один session_id**

### Использование:

```javascript
// ✅ ПРАВИЛЬНО: Visual grouping по session_id
const groupedBySession = useMemo(() => {
  const groups = {};
  entries.forEach(e => {
    const key = e.session_id || e.id; // Fallback на ID
    if (!groups[key]) groups[key] = [];
    groups[key].push(e);
  });
  return groups;
}, [entries]);

// ❌ ЗАПРЕЩЕНО: Парсинг формата session_id
const [patientId, queueId, date] = session_id.split('_'); // ЗАПРЕЩЕНО
```

---

*Последнее обновление: 2025-12-26*

