# 🏥 MediLab UI - Унифицированный дизайн медицинской системы

## 📋 Обзор

Этот документ описывает новую унифицированную систему дизайна, созданную на основе эталонного дизайна MediLab. Система обеспечивает единообразный, современный и профессиональный интерфейс для всех панелей медицинской клиники.

## 🎯 Основные цели

- ✅ **Единообразие** - Все панели используют одинаковый дизайн
- ✅ **Современность** - Соответствие современным стандартам UI/UX
- ✅ **Медицинская специфика** - Специализированные компоненты для медицины
- ✅ **Адаптивность** - Работа на всех устройствах
- ✅ **Производительность** - Оптимизированный код без дублирований

## 🚀 Быстрый старт

### Демонстрация
Откройте в браузере: `http://localhost:5173/medilab-demo`

### Использование в существующих панелях

```jsx
import UnifiedLayout from '../components/UnifiedLayout';
import { MedicalCard, PatientCard, MetricCard, MedicalTable } from '../components/medical';

const YourPanel = () => {
  return (
    <UnifiedLayout showSidebar={true}>
      <div className="space-y-6">
        {/* Ваш контент здесь */}
        <MedicalCard>
          <h2>Заголовок</h2>
          <p>Содержимое карточки</p>
        </MedicalCard>
      </div>
    </UnifiedLayout>
  );
};
```

## 🧩 Компоненты

### 1. UnifiedLayout
Основной макет с сайдбаром и контентом.

```jsx
<UnifiedLayout showSidebar={true}>
  {children}
</UnifiedLayout>
```

**Пропсы:**
- `showSidebar` (boolean) - Показывать ли сайдбар
- `children` - Контент панели

### 2. UnifiedSidebar
Унифицированный сайдбар в стиле MediLab.

**Особенности:**
- Автоматическое определение роли пользователя
- Адаптивное сворачивание
- Мобильная версия
- Темная/светлая тема

### 3. MedicalCard
Базовая карточка для медицинского контента.

```jsx
<MedicalCard 
  hover={true}
  padding="medium"
  shadow="medium"
>
  <h3>Заголовок</h3>
  <p>Содержимое</p>
</MedicalCard>
```

**Пропсы:**
- `hover` (boolean) - Эффект при наведении
- `padding` ('small' | 'medium' | 'large') - Размер отступов
- `shadow` ('none' | 'small' | 'medium' | 'large') - Размер тени

### 4. PatientCard
Карточка пациента с аватаром и действиями.

```jsx
<PatientCard
  patient={{
    id: 1,
    name: 'John Doe',
    patientId: 'P001234',
    age: 45,
    gender: 'M',
    lastVisit: '2 days ago',
    department: 'Cardiology',
    status: 'active'
  }}
  onView={(patient) => console.log('View:', patient)}
  onEdit={(patient) => console.log('Edit:', patient)}
  onDelete={(patient) => console.log('Delete:', patient)}
/>
```

### 5. MetricCard
Карточка метрики для дашборда.

```jsx
<MetricCard
  title="Total Patients"
  value="1,247"
  change={12.5}
  icon={Users}
  color="blue"
/>
```

**Пропсы:**
- `title` (string) - Заголовок метрики
- `value` (string) - Значение
- `change` (number) - Изменение в процентах
- `icon` (Component) - Иконка
- `color` ('blue' | 'green' | 'purple' | 'orange' | 'red') - Цветовая схема

### 6. MedicalTable
Унифицированная таблица с действиями.

```jsx
<MedicalTable
  columns={[
    { key: 'name', label: 'Name' },
    { key: 'email', label: 'Email' },
    { key: 'status', label: 'Status', render: (value) => <Badge>{value}</Badge> }
  ]}
  data={users}
  onView={(user) => console.log('View:', user)}
  onEdit={(user) => console.log('Edit:', user)}
  onDelete={(user) => console.log('Delete:', user)}
  sortable={true}
  pagination={true}
  pageSize={10}
/>
```

## 🎨 Стилизация

### CSS переменные
Система использует CSS переменные для тем:

```css
:root {
  --bg-primary: #ffffff;
  --bg-secondary: #f8fafc;
  --text-primary: #1e293b;
  --text-secondary: #64748b;
  --border-color: #e2e8f0;
  --accent-color: #3b82f6;
}
```

### Темная тема
```css
[data-theme="dark"] {
  --bg-primary: #1e293b;
  --bg-secondary: #0f172a;
  --text-primary: #f8fafc;
  --text-secondary: #94a3b8;
  --border-color: #334155;
}
```

## 📱 Адаптивность

Система автоматически адаптируется под размер экрана:

- **Desktop** (>1024px) - Полный сайдбар
- **Tablet** (768px-1024px) - Сворачиваемый сайдбар
- **Mobile** (<768px) - Скрытый сайдбар с оверлеем

## 🔧 Настройка

### Добавление новых пунктов навигации

В `UnifiedSidebar.jsx`:

```jsx
const mainNavItems = [
  // ... существующие элементы
  {
    id: 'new-section',
    label: 'New Section',
    icon: NewIcon,
    path: '/new-section',
    roles: ['admin', 'doctor'] // Роли, которые могут видеть этот пункт
  }
];
```

### Создание новых медицинских компонентов

1. Создайте файл в `src/components/medical/`
2. Используйте `useTheme` для поддержки тем
3. Экспортируйте в `src/components/medical/index.js`

## 📊 Демонстрационные данные

Демонстрационная страница включает:

- **Dashboard** - Метрики и быстрые действия
- **Patients** - Карточки пациентов с аватарами
- **Appointments** - Таблица записей
- **Staff Schedule** - Расписание персонала (Gantt-диаграмма)

## 🚧 Планы развития

### Фаза 2 (В разработке)
- [ ] Улучшенный календарь записей
- [ ] Полноценная Gantt-диаграмма для расписания
- [ ] Медицинские формы и валидация
- [ ] Интеграция с существующими панелями

### Фаза 3 (Планируется)
- [ ] Удаление дублирований в коде
- [ ] Оптимизация производительности
- [ ] Расширенная система тем
- [ ] Мобильное приложение

## 🐛 Известные проблемы

- Некоторые существующие панели еще не переведены на новый дизайн
- Gantt-диаграмма в демо-версии упрощенная
- Некоторые анимации могут работать медленно на старых устройствах

## 🤝 Участие в разработке

1. Создайте ветку для новой функции
2. Следуйте существующим паттернам кода
3. Добавьте тесты для новых компонентов
4. Обновите документацию

## 📞 Поддержка

При возникновении проблем:
1. Проверьте консоль браузера на ошибки
2. Убедитесь, что все зависимости установлены
3. Проверьте совместимость с существующим кодом

---

**Создано:** 2024  
**Версия:** 1.0.0  
**Статус:** В активной разработке
