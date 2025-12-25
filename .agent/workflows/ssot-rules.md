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

## При нарушении правил:

1. **Остановись** — не продолжай работу
2. **Сообщи пользователю** — укажи какое правило нарушается
3. **Предложи SSOT решение** — покажи как сделать правильно
4. **Создай тикет для backend** — если данные отсутствуют в API

---

*Последнее обновление: 2025-12-24*
