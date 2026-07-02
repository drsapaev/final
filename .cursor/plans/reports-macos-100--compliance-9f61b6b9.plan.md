<!-- 9f61b6b9-000c-44eb-9d11-c8b863e0fd61 73836d8f-69f6-4f96-9c9e-c9446e60f6c7 -->
# План улучшения EMR системы

## Этап 1: Критичная функциональность (EMRInterface.jsx)

### 1.1 Реализация операций с записями

**Файл**: `frontend/src/components/medical/EMRInterface.jsx`

- Добавить `handleUpdateRecord` функцию для обновления существующих медицинских записей через API PUT/PATCH запрос
- Добавить `handleDeleteRecord` функцию для удаления записей через API DELETE запрос
- Реализовать состояние для диалога подтверждения удаления (`showDeleteDialog`, `recordToDelete`)
- Создать компонент диалога подтверждения с кнопками "Отмена" и "Удалить"

### 1.2 Операции с шаблонами

**Файл**: `frontend/src/components/medical/EMRInterface.jsx`

- Добавить `handleEditTemplate` и `handleDeleteTemplate` функции
- Подключить обработчики к кнопкам Edit и Delete в секции шаблонов
- Реализовать диалог редактирования шаблона (аналогично диалогу записи)

### 1.3 Улучшенный маппинг полей

**Файл**: `frontend/src/components/medical/EMRInterface.jsx`

- Обновить функцию `openRecordDialog` для явного маппинга полей из `record` в `recordForm`
- Добавить функцию `resetRecordForm` для очистки формы
- Гарантировать, что все поля формы корректно инициализируются

---

## Этап 2: UX улучшения (EMRInterface.jsx)

### 2.1 Оптимизация стилей

**Файл**: `frontend/src/components/medical/EMRInterface.jsx`

- Создать функцию `tabButtonStyle(isActive)` для унификации стилей кнопок вкладок
- Применить функцию ко всем трем кнопкам вкладок (Пациенты, Медицинские записи, Шаблоны)

### 2.2 Улучшение таблицы записей

**Файл**: `frontend/src/components/medical/EMRInterface.jsx`

- Убрать отображение `ID: {record.patient_id}` из таблицы медицинских записей
- Оставить только `patient?.full_name` для лучшей читаемости

### 2.3 Структурирование формы записи

**Файл**: `frontend/src/components/medical/EMRInterface.jsx`

- Разбить большую форму создания/редактирования записи на секции:
  - "Основная информация" (пациент, тип записи)
  - "Жалобы и анамнез" (complaints, history_of_present_illness)
  - "Осмотр и диагностика" (physical_examination, diagnosis)
  - "План лечения" (plan, treatment_notes, follow_up_instructions)
- Использовать HTML `<details>` элементы или создать простой аккордеон компонент

---

## Этап 3: Обработка ошибок (EMRInterface.jsx)

### 3.1 Детальная обработка HTTP ошибок

**Файл**: `frontend/src/components/medical/EMRInterface.jsx`

- Создать функцию `handleApiError(error)` для централизованной обработки ошибок
- Добавить специфичные сообщения для:
  - 401 (Unauthorized) - "Сессия истекла, войдите снова"
  - 404 (Not Found) - "Ресурс не найден"
  - 500 (Server Error) - "Ошибка сервера, попробуйте позже"
  - Network errors - "Проблема с подключением к серверу"

### 3.2 Toast уведомления

**Файл**: `frontend/src/components/medical/EMRInterface.jsx`

- Заменить простые Alert на Toast уведомления (если доступны из `../ui/macos`)
- Добавить Toast для успешных операций (создание, обновление, удаление)
- Добавить Toast для ошибок с автоматическим закрытием

---

## Этап 4: AI оптимизация (EMRSystem.jsx)

### 4.1 Кэширование AI результатов

**Файл**: `frontend/src/components/medical/EMRSystem.jsx`

- Добавить состояние `complaintsAnalysisCache` для хранения результатов `analyzeComplaints`
- Вызывать `analyzeComplaints` только при изменении `complaints` (с debounce)
- Использовать кэшированные результаты для заполнения анамнеза, осмотра и рекомендаций

### 4.2 Константы для AI

**Файл**: `frontend/src/components/medical/EMRSystem.jsx` или новый `constants/ai.js`

- Создать константы:
  ```javascript
  export const AI_ANALYSIS_TYPES = {
    COMPLAINT: 'complaint',
    ANAMNESIS: 'anamnesis',
    EXAMINATION: 'examination',
    RECOMMENDATION: 'recommendation'
  };
  
  export const MCP_PROVIDERS = {
    DEEPSEEK: 'deepseek',
    GEMINI: 'gemini'
  };
  ```

- Заменить все магические строки на константы

### 4.3 Отображение AI ошибок

**Файл**: `frontend/src/components/medical/EMRSystem.jsx`

- Добавить `<Alert severity="error">{aiError}</Alert>` в UI компонент
- Разместить Alert над формой или в верхней части интерфейса
- Добавить кнопку закрытия ошибки

---

## Этап 5: Загрузка файлов (EMRSystem.jsx)

### 5.1 Выбор категории вложений

**Файл**: `frontend/src/components/medical/EMRSystem.jsx`

- Добавить Select для выбора категории перед загрузкой файла:
  - 'examination' - Обследование
  - 'documents' - Документы
  - 'before_after' - До/После
  - 'lab_results' - Анализы
- Сохранять выбранную категорию в состояние `selectedCategory`

### 5.2 Миниатюры изображений

**Файл**: `frontend/src/components/medical/EMRSystem.jsx`

- Отображать миниатюры загруженных изображений в grid layout
- Добавить превью для файлов: изображения показывать, для остальных - иконку типа файла
- Показывать имя файла под миниатюрой

### 5.3 Удаление вложений

**Файл**: `frontend/src/components/medical/EMRSystem.jsx`

- Добавить кнопку "X" или иконку Trash2 на каждую миниатюру
- Реализовать `handleRemoveAttachment(index)` функцию
- Добавить подтверждение перед удалением

### 5.4 Drag-and-Drop

**Файл**: `frontend/src/components/medical/EMRSystem.jsx`

- Добавить область для drag-and-drop с обработчиками:
  - `onDragOver` - предотвратить default и показать визуальную подсказку
  - `onDrop` - обработать загрузку файлов
- Добавить визуальный индикатор зоны drop (пунктирная рамка, текст "Перетащите файлы сюда")

---

## Этап 6: Система сохранения данных (EMRSystem.jsx)

### 6.1 Предупреждение о несохраненных изменениях

**Файл**: `frontend/src/components/medical/EMRSystem.jsx`

- Добавить `useEffect` с обработчиком `window.onbeforeunload`
- Показывать предупреждение браузера при попытке закрыть вкладку с `hasUnsavedChanges === true`
- Очищать обработчик при размонтировании компонента

### 6.2 Автосохранение черновиков

**Файл**: `frontend/src/components/medical/EMRSystem.jsx`

- Добавить `useEffect` с интервалом автосохранения (каждые 30 секунд)
- Создать функцию `autoSaveDraft()` для тихого сохранения в фоне
- Показывать индикатор "Сохранено автоматически" с временной меткой

### 6.3 Явное сохранение черновика

**Файл**: `frontend/src/components/medical/EMRSystem.jsx`

- Добавить кнопку "Сохранить черновик" рядом с кнопкой "Завершить прием"
- Создать функцию `handleSaveDraft()` с параметром `isDraft: true`
- Обновлять UI после сохранения черновика (показать Toast "Черновик сохранен")

---

## Общие улучшения

### Порядок реализации по приоритету:

1. **Этап 1** (критично) - без этого система не полнофункциональна
2. **Этап 3** (важно) - улучшает UX и предотвращает ошибки
3. **Этап 6.1** (важно) - предотвращает потерю данных
4. **Этап 2** (средний) - улучшает визуальную часть
5. **Этап 4** (средний) - оптимизирует работу AI
6. **Этап 5** (желательно) - улучшает работу с файлами
7. **Этапы 6.2-6.3** (опционально) - дополнительные удобства

### Файлы для изменения:

- `frontend/src/components/medical/EMRInterface.jsx` - основной файл для этапов 1-3
- `frontend/src/components/medical/EMRSystem.jsx` - основной файл для этапов 4-6
- `frontend/src/constants/ai.js` - новый файл для констант AI (этап 4.2)

### To-dos

- [x] 