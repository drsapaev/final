# 🎯 Отключение старого мастера регистрации

**Дата:** 2025-10-01  
**Статус:** ✅ Завершено

## 📋 Выполненные действия:

### 1. Изменен дефолт в `useWizardSettings.js`
Теперь по умолчанию используется **НОВЫЙ мастер (V2)**:
```javascript
use_new_wizard: true  // Было: false
```

### 2. Переименован старый мастер
`AppointmentWizard.jsx` → `AppointmentWizard.OLD.jsx`

**Местоположение:** `frontend/src/components/wizard/AppointmentWizard.OLD.jsx`

### 3. Удален код старого мастера из `RegistrarPanel.jsx`
- ✅ Удален импорт `AppointmentWizard`
- ✅ Удален условный рендеринг (`useNewWizard ? ... : ...`)
- ✅ Удалено 249 строк кода обработки старого мастера
- ✅ Размер файла: 3638 → 3389 строк

### 4. Упрощена структура
Теперь `RegistrarPanel.jsx` использует только `AppointmentWizardV2` без условий.

## 🔧 Технические детали:

### Старый мастер (`AppointmentWizard.OLD.jsx`)
- ❌ Создавал визиты через старый API `/api/v1/appointments/`
- ❌ Не использовал корзину (`/registrar/cart`)
- ❌ Не группировал услуги по department
- ❌ Требовал ручную обработку doctor_id, department, services
- ❌ Не присваивал номера в очередях автоматически

### Новый мастер (`AppointmentWizardV2.jsx`)
- ✅ Использует унифицированный API корзины `/api/v1/registrar/cart`
- ✅ Автоматически группирует услуги по department
- ✅ Поддерживает множественные визиты одного пациента
- ✅ Автоматическое присвоение номеров в очередях для визитов на сегодня
- ✅ Поддержка льготных/повторных визитов
- ✅ Интеграция с `MorningAssignmentService`

## 🗂️ Файлы

### Изменены:
- `frontend/src/hooks/useWizardSettings.js`
- `frontend/src/pages/RegistrarPanel.jsx`

### Переименованы:
- `frontend/src/components/wizard/AppointmentWizard.jsx` → `AppointmentWizard.OLD.jsx`

## 🔄 Откат (если понадобится):

1. Переименуйте обратно:
   ```bash
   cd frontend/src/components/wizard
   move AppointmentWizard.OLD.jsx AppointmentWizard.jsx
   ```

2. Измените дефолт в `useWizardSettings.js`:
   ```javascript
   use_new_wizard: false
   ```

3. Восстановите условный рендеринг в `RegistrarPanel.jsx` из git истории

## ⚠️ Важно!

После этих изменений **старый мастер НЕДОСТУПЕН** в интерфейсе. Все регистрации теперь проходят через новый мастер (V2).

## 📊 Результаты:

- ✅ Упрощен код на 249 строк
- ✅ Убрана зависимость от хука `useWizardSettings` 
- ✅ Улучшена производительность (меньше условных проверок)
- ✅ Уменьшен размер bundle (старый мастер не загружается)
- ✅ Все функции работают через новый мастер

---

**Примечание:** Старый мастер сохранен как `AppointmentWizard.OLD.jsx` на случай необходимости отката или справки.

