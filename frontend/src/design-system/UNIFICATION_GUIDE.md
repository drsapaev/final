# 🎨 Руководство по унификации UI/UX

## 📋 Обзор

Это руководство поможет унифицировать все панели клиники под единую дизайн-систему для обеспечения консистентного пользовательского опыта.

## 🎯 Цели унификации

- ✅ **Единообразие** - все панели выглядят и работают одинаково
- ✅ **Адаптивность** - корректное отображение на всех устройствах
- ✅ **Доступность** - поддержка всех категорий пользователей
- ✅ **Производительность** - быстрая загрузка и плавные анимации
- ✅ **Масштабируемость** - легкое добавление новых панелей

## 🏗️ Архитектура дизайн-системы

### Структура файлов:
```
src/design-system/
├── theme/
│   ├── medical.js           # Медицинская тема
│   ├── colors.js           # Цветовая палитра
│   ├── typography.js       # Типографика
│   └── spacing.js          # Отступы и размеры
├── components/
│   ├── MedicalCard.jsx     # Унифицированная карточка
│   ├── Button.jsx          # Кнопки
│   ├── Card.jsx           # Базовые карточки
│   └── Badge.jsx          # Бейджи
├── layouts/
│   └── ResponsiveLayout.jsx # Адаптивные макеты
├── hooks/
│   ├── useBreakpoint.js    # Адаптивные хуки
│   └── useTheme.js         # Хуки тем
└── styles/
    ├── animations.css      # Анимации
    └── responsive.css      # Адаптивные стили
```

## 🎨 Медицинская тема

### Цветовая палитра по отделениям:

```javascript
import { medicalTheme, getDepartmentStyle } from '../design-system/theme/medical';

// Кардиология - красный
const cardioStyle = getDepartmentStyle('cardiology');
// { background: 'linear-gradient(...)', accent: '#dc2626', icon: '❤️' }

// Дерматология - оранжевый  
const dermaStyle = getDepartmentStyle('dermatology');
// { background: 'linear-gradient(...)', accent: '#f59e0b', icon: '🧴' }

// Стоматология - синий
const dentistryStyle = getDepartmentStyle('dentistry');
// { background: 'linear-gradient(...)', accent: '#3b82f6', icon: '🦷' }

// Лаборатория - фиолетовый
const labStyle = getDepartmentStyle('laboratory');
// { background: 'linear-gradient(...)', accent: '#8b5cf6', icon: '🔬' }
```

### Статусы пациентов:

```javascript
import { getPatientStatusStyle } from '../design-system/theme/medical';

const healthyStyle = getPatientStatusStyle('healthy');
const sickStyle = getPatientStatusStyle('sick');
const recoveryStyle = getPatientStatusStyle('recovery');
```

## 🧩 Унифицированные компоненты

### 1. MedicalCard - Основная карточка

```javascript
import MedicalCard from '../design-system/components/MedicalCard';

// Карточка пациента
<MedicalCard
  patient={{
    name: "Иванов Иван Иванович",
    phone: "+998901234567",
    email: "ivan@example.com"
  }}
  appointment={{
    date: "2025-01-15",
    time: "10:30",
    totalAmount: 150000
  }}
  department="cardiology"
  status="confirmed"
  priority="normal"
  actions={[
    { label: "Редактировать", onClick: handleEdit },
    { label: "Удалить", onClick: handleDelete, variant: "danger" }
  ]}
  onCardClick={handleCardClick}
/>

// Компактная карточка
<MedicalCard
  variant="compact"
  title="Консультация кардиолога"
  subtitle="15 января 2025, 10:30"
  status="scheduled"
  department="cardiology"
/>

// Детальная карточка
<MedicalCard
  variant="detailed"
  patient={patientData}
  appointment={appointmentData}
  services={servicesData}
  department="dermatology"
  showActions={true}
  showBadges={true}
/>
```

### 2. ResponsiveLayout - Адаптивный макет

```javascript
import ResponsiveLayout, { SidebarNav, QuickActions } from '../design-system/layouts/ResponsiveLayout';

const MyPanel = () => {
  const sidebarItems = [
    { id: 'patients', label: 'Пациенты', icon: User },
    { id: 'appointments', label: 'Записи', icon: Calendar },
    { id: 'queue', label: 'Очередь', icon: Clock, badge: 5 }
  ];

  const quickActions = [
    { label: 'Новый пациент', icon: Plus, onClick: handleNewPatient, variant: 'primary' },
    { label: 'Печать', icon: Printer, onClick: handlePrint }
  ];

  return (
    <ResponsiveLayout
      title="Панель кардиолога"
      subtitle="Управление пациентами и записями"
      theme="medical"
      sidebar={<SidebarNav items={sidebarItems} onItemClick={handleNavClick} />}
      headerActions={<QuickActions actions={quickActions} />}
    >
      {/* Основной контент панели */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {patients.map(patient => (
          <MedicalCard key={patient.id} patient={patient} department="cardiology" />
        ))}
      </div>
    </ResponsiveLayout>
  );
};
```

## 📱 Адаптивные принципы

### Breakpoints:
- **Mobile**: до 768px - одна колонка, крупные кнопки
- **Tablet**: 769px-1024px - две колонки, средние элементы  
- **Desktop**: 1025px+ - три+ колонки, компактные элементы

### Адаптивные хуки:

```javascript
import { useBreakpoint, useTouchDevice } from '../design-system/hooks';

const MyComponent = () => {
  const { isMobile, isTablet, isDesktop } = useBreakpoint();
  const isTouch = useTouchDevice();

  return (
    <div className={`
      ${isMobile ? 'p-4' : 'p-6'}
      ${isTouch ? 'min-h-[44px]' : 'min-h-[32px]'}
    `}>
      {isMobile ? <MobileLayout /> : <DesktopLayout />}
    </div>
  );
};
```

## 🎭 Анимации и переходы

### Стандартные анимации:

```css
/* Появление карточек */
.fade-in {
  animation: fadeIn 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

/* Hover эффекты */
.card-hover:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
}

/* Пульсация для критичных элементов */
.pulse-emergency {
  animation: pulse 1s infinite;
}

/* Сердцебиение для кардиологии */
.heartbeat {
  animation: heartbeat 1.5s ease-in-out infinite;
}
```

### Использование в компонентах:

```javascript
import { medicalTheme } from '../design-system/theme/medical';

const EmergencyCard = () => (
  <div 
    className="emergency-card"
    style={{
      animation: medicalTheme.animations.pulse.keyframes,
      animationDuration: medicalTheme.animations.pulse.duration
    }}
  >
    Экстренный пациент
  </div>
);
```

## 📋 Чек-лист миграции панелей

### Для каждой панели:

#### ✅ Структура и макет
- [ ] Заменить кастомные макеты на `ResponsiveLayout`
- [ ] Добавить адаптивную навигацию `SidebarNav`
- [ ] Реализовать быстрые действия `QuickActions`
- [ ] Настроить правильные breakpoints

#### ✅ Компоненты
- [ ] Заменить кастомные карточки на `MedicalCard`
- [ ] Использовать унифицированные `Button`, `Badge`, `Card`
- [ ] Применить медицинскую тему для отделения
- [ ] Добавить правильные статусы и приоритеты

#### ✅ Стилизация
- [ ] Заменить хардкод цвета на токены из `medicalTheme`
- [ ] Применить правильные градиенты для отделения
- [ ] Добавить стандартные анимации и переходы
- [ ] Настроить темную/светлую темы

#### ✅ Адаптивность
- [ ] Протестировать на мобильных устройствах
- [ ] Проверить touch-friendly элементы (минимум 44px)
- [ ] Убедиться в корректной работе sidebar на мобильных
- [ ] Оптимизировать для планшетов

#### ✅ Доступность
- [ ] Добавить ARIA атрибуты
- [ ] Обеспечить keyboard navigation
- [ ] Проверить цветовые контрасты
- [ ] Поддержать screen readers

## 🔄 Пошаговая миграция

### Шаг 1: Подготовка
```bash
# Убедитесь, что дизайн-система импортирована
import { 
  medicalTheme, 
  getDepartmentStyle,
  getPatientStatusStyle 
} from '../design-system/theme/medical';

import MedicalCard from '../design-system/components/MedicalCard';
import ResponsiveLayout from '../design-system/layouts/ResponsiveLayout';
```

### Шаг 2: Замена макета
```javascript
// ❌ Было
const MyPanel = () => (
  <div className="custom-panel">
    <header>...</header>
    <aside>...</aside>
    <main>...</main>
  </div>
);

// ✅ Стало
const MyPanel = () => (
  <ResponsiveLayout
    title="Название панели"
    theme="medical"
    sidebar={<SidebarNav items={navItems} />}
  >
    {/* контент */}
  </ResponsiveLayout>
);
```

### Шаг 3: Замена карточек
```javascript
// ❌ Было
const PatientCard = ({ patient }) => (
  <div className="patient-card">
    <h3>{patient.name}</h3>
    <p>{patient.phone}</p>
    <span className={`status-${patient.status}`}>
      {patient.status}
    </span>
  </div>
);

// ✅ Стало
const PatientCard = ({ patient }) => (
  <MedicalCard
    patient={patient}
    department="cardiology"
    status={patient.status}
    variant="compact"
  />
);
```

### Шаг 4: Применение темы
```javascript
// ❌ Было
const cardStyle = {
  background: '#ff0000',
  border: '1px solid #ccc'
};

// ✅ Стало
const departmentStyle = getDepartmentStyle('cardiology');
const cardStyle = {
  background: departmentStyle.background,
  borderLeft: `4px solid ${departmentStyle.accent}`
};
```

## 🎯 Панели для миграции

### Приоритет 1 (Критичные):
1. **RegistrarPanel** - основная панель регистратуры
2. **DoctorPanel** - базовая панель врача
3. **AppointmentWizardV2** - мастер записи

### Приоритет 2 (Важные):
4. **CardiologistPanelUnified** - панель кардиолога
5. **DermatologistPanelUnified** - панель дерматолога  
6. **DentistPanelUnified** - панель стоматолога

### Приоритет 3 (Дополнительные):
7. **LabPanel** - лабораторная панель
8. **AdminPanel** - административная панель
9. **CashierPanel** - панель кассира

## 📊 Метрики успеха

### До унификации:
- 🔴 Разные стили в каждой панели
- 🔴 Проблемы с адаптивностью
- 🔴 Дублирование кода
- 🔴 Сложность поддержки

### После унификации:
- 🟢 Единый стиль во всех панелях
- 🟢 Корректная работа на всех устройствах  
- 🟢 Переиспользование компонентов
- 🟢 Легкая поддержка и развитие

## 🚀 Результат

После завершения унификации получим:

- **📱 Адаптивный дизайн** - корректная работа на всех устройствах
- **🎨 Единый стиль** - консистентный внешний вид
- **⚡ Высокая производительность** - оптимизированные компоненты
- **♿ Доступность** - поддержка всех пользователей
- **🔧 Легкая поддержка** - централизованная дизайн-система
- **📈 Масштабируемость** - простое добавление новых панелей

## 📞 Поддержка

При возникновении вопросов:
1. Изучите примеры в `design-system/components/`
2. Проверьте документацию в README.md
3. Посмотрите на уже мигрированные панели
4. Обратитесь к команде разработки
