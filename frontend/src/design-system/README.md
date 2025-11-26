# 🏥 Улучшенная дизайн-система для медицинских интерфейсов

## 📋 Обзор

Эта дизайн-система создана специально для медицинских интерфейсов и основана на принципах:

- **Доступности** (WCAG 2.1 AA)
- **Медицинских стандартов UX**
- **Производительности**
- **Консистентности**
- **Масштабируемости**

## 🚀 Быстрый старт

### Установка

```bash
# Установка зависимостей
npm install clsx lucide-react

# Импорт в проект
import { DESIGN_SYSTEM } from './design-system';
```

### Базовое использование

```jsx
import React from 'react';
import { 
  ThemeProvider, 
  Button, 
  Card, 
  useTheme 
} from './design-system';

function App() {
  return (
    <ThemeProvider>
      <Card>
        <Button variant="primary" size="md">
          Создать запись
        </Button>
      </Card>
    </ThemeProvider>
  );
}
```

## 🎨 Дизайн-токены

### Цвета

```jsx
import { getColor } from './design-system';

// Основные цвета
const primaryColor = getColor('primary.500'); // #0066cc
const successColor = getColor('medical.success'); // #10b981
const dangerColor = getColor('medical.danger'); // #ef4444

// Семантические цвета
const textColor = getColor('text.primary'); // #1e293b
const bgColor = getColor('background.primary'); // #ffffff
const borderColor = getColor('border.primary'); // #e2e8f0
```

### Типографика

```jsx
import { getFontSize, getFontWeight } from './design-system';

const styles = {
  fontSize: getFontSize('xl'), // 20px
  fontWeight: getFontWeight('semibold'), // 600
  lineHeight: '1.5'
};
```

### Отступы и размеры

```jsx
import { getSpacing, getBorderRadius, getShadow } from './design-system';

const styles = {
  padding: getSpacing('lg'), // 24px
  borderRadius: getBorderRadius('md'), // 8px
  boxShadow: getShadow('md') // 0 4px 6px -1px rgba(0, 0, 0, 0.1)
};
```

## 🧩 Компоненты

### Кнопки

```jsx
import { Button } from './design-system';

// Различные варианты
<Button variant="primary" size="md">Основная</Button>
<Button variant="success" size="lg">Успех</Button>
<Button variant="danger" size="sm">Опасность</Button>
<Button variant="outline" size="md">Контурная</Button>
<Button variant="ghost" size="md">Прозрачная</Button>

// Медицинские кнопки
<Button variant="medical" size="lg">Медицинская</Button>

// Состояния
<Button loading={true}>Загрузка...</Button>
<Button disabled={true}>Отключена</Button>
<Button fullWidth={true}>На всю ширину</Button>
```

### Карточки

```jsx
import { Card } from './design-system';

// Различные варианты
<Card variant="default" padding="md">
  <h3>Заголовок</h3>
  <p>Содержимое карточки</p>
</Card>

<Card variant="elevated" padding="lg" shadow="lg">
  <h3>Приподнятая карточка</h3>
</Card>

<Card variant="medical" padding="md">
  <h3>Медицинская карточка</h3>
</Card>
```

### Формы

```jsx
import { FormField, FormTextarea, FormSelect, useForm } from './design-system';

function PatientForm() {
  const { values, errors, handleChange, handleBlur, handleSubmit } = useForm(
    { name: '', email: '', phone: '' },
    {
      name: [validators.required, validators.minLength(2)],
      email: [validators.required, validators.email],
      phone: [validators.required, validators.phone]
    }
  );

  return (
    <form onSubmit={handleSubmit}>
      <FormField
        name="name"
        label="ФИО"
        value={values.name}
        onChange={handleChange}
        onBlur={handleBlur}
        error={errors.name}
        required
      />
      
      <FormField
        name="email"
        label="Email"
        type="email"
        value={values.email}
        onChange={handleChange}
        onBlur={handleBlur}
        error={errors.email}
        required
      />
      
      <FormTextarea
        name="notes"
        label="Примечания"
        value={values.notes}
        onChange={handleChange}
        onBlur={handleBlur}
        rows={4}
      />
    </form>
  );
}
```

### Таблицы

```jsx
import { Table, useTable } from './design-system';

function AppointmentsTable({ data }) {
  const columns = [
    { key: 'id', title: 'ID', sortable: true },
    { key: 'patient', title: 'Пациент', sortable: true },
    { key: 'date', title: 'Дата', sortable: true },
    { key: 'status', title: 'Статус', render: (value) => (
      <Badge variant={value === 'completed' ? 'success' : 'warning'}>
        {value}
      </Badge>
    )},
    { key: 'actions', title: 'Действия', render: (_, row) => (
      <Button size="sm" onClick={() => handleEdit(row)}>
        Редактировать
      </Button>
    )}
  ];

  return (
    <Table
      data={data}
      columns={columns}
      options={{
        pageSize: 10,
        sortable: true,
        filterable: true,
        selectable: true,
        searchable: true
      }}
    />
  );
}
```

### Модальные окна

```jsx
import { Modal, ModalWithActions, ConfirmModal, useModal } from './design-system';

function App() {
  const { isOpen, openModal, closeModal } = useModal();

  return (
    <>
      <Button onClick={openModal}>Открыть модальное окно</Button>
      
      <Modal
        isOpen={isOpen}
        onClose={closeModal}
        title="Создание записи"
        size="lg"
      >
        <p>Содержимое модального окна</p>
      </Modal>
    </>
  );
}

// Модальное окно с действиями
function ConfirmDialog() {
  const { isOpen, openModal, closeModal } = useModal();

  const handleConfirm = async () => {
    // Логика подтверждения
    closeModal();
  };

  return (
    <ModalWithActions
      isOpen={isOpen}
      onClose={closeModal}
      onConfirm={handleConfirm}
      title="Подтверждение"
      confirmText="Удалить"
      cancelText="Отмена"
      confirmVariant="danger"
    >
      <p>Вы уверены, что хотите удалить эту запись?</p>
    </ModalWithActions>
  );
}
```

### Уведомления

```jsx
import { NotificationProvider, useNotifications } from './design-system';

function App() {
  return (
    <NotificationProvider>
      <MainContent />
    </NotificationProvider>
  );
}

function MainContent() {
  const { success, error, warning, info, medical, emergency } = useNotifications();

  const handleSuccess = () => {
    success('Запись успешно создана!');
  };

  const handleError = () => {
    error('Произошла ошибка при создании записи');
  };

  const handleMedical = () => {
    medical('Пациент направлен на дополнительное обследование');
  };

  const handleEmergency = () => {
    emergency('Требуется срочная медицинская помощь!', {
      persistent: true,
      actions: [
        { label: 'Вызвать скорую', onClick: () => console.log('Скорая вызвана') }
      ]
    });
  };

  return (
    <div>
      <Button onClick={handleSuccess}>Успех</Button>
      <Button onClick={handleError}>Ошибка</Button>
      <Button onClick={handleMedical}>Медицинское</Button>
      <Button onClick={handleEmergency}>Экстренное</Button>
    </div>
  );
}
```

## 🎯 Хуки

### Темизация

```jsx
import { useTheme } from './design-system';

function ThemedComponent() {
  const { theme, isDark, isLight, toggleTheme, getColor, getSpacing } = useTheme();

  return (
    <div style={{ 
      backgroundColor: getColor('background.primary'),
      color: getColor('text.primary'),
      padding: getSpacing('lg')
    }}>
      <h1>Текущая тема: {theme}</h1>
      <Button onClick={toggleTheme}>
        Переключить тему
      </Button>
    </div>
  );
}
```

### Адаптивность

```jsx
import { useBreakpoint, useDevice, useMediaQuery } from './design-system';

function ResponsiveComponent() {
  const { isMobile, isTablet, isDesktop } = useBreakpoint();
  const { device } = useDevice();
  const { isTouchDevice, hasHoverSupport } = useMediaQuery();

  return (
    <div>
      <p>Устройство: {device}</p>
      <p>Мобильное: {isMobile ? 'Да' : 'Нет'}</p>
      <p>Планшет: {isTablet ? 'Да' : 'Нет'}</p>
      <p>Десктоп: {isDesktop ? 'Да' : 'Нет'}</p>
      <p>Touch устройство: {isTouchDevice ? 'Да' : 'Нет'}</p>
      <p>Поддержка hover: {hasHoverSupport ? 'Да' : 'Нет'}</p>
    </div>
  );
}
```

### AI-интеграция

```jsx
import { useAIAssistant, useAISuggestions } from './design-system';

function MedicalAI() {
  const { analyzeMedicalData, generateRecommendations, loading, error } = useAIAssistant({
    provider: 'deepseek',
    context: 'medical'
  });

  const { suggestions, searchSuggestions } = useAISuggestions({
    context: 'medical'
  });

  const handleAnalyze = async () => {
    try {
      const result = await analyzeMedicalData({
        symptoms: 'Головная боль, тошнота',
        temperature: 37.5
      }, 'symptoms');
      
      console.log('Результат анализа:', result);
    } catch (err) {
      console.error('Ошибка анализа:', err);
    }
  };

  return (
    <div>
      <Button onClick={handleAnalyze} loading={loading}>
        Анализировать симптомы
      </Button>
      
      {error && <p>Ошибка: {error}</p>}
      
      {suggestions.length > 0 && (
        <ul>
          {suggestions.map((suggestion, index) => (
            <li key={index}>{suggestion}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

### Анимации

```jsx
import { useAnimation, AnimatedTransition, AnimatedList } from './design-system';

function AnimatedComponent() {
  const [isVisible, setIsVisible] = useState(false);
  const { shouldRender, animationClasses } = useAnimation(isVisible, 'slideUp', 300);

  return (
    <div>
      <Button onClick={() => setIsVisible(!isVisible)}>
        Переключить видимость
      </Button>
      
      <AnimatedTransition isVisible={isVisible} animationType="fade">
        <Card>Анимированная карточка</Card>
      </AnimatedTransition>
    </div>
  );
}

// Анимированный список
function AnimatedAppointmentsList({ appointments }) {
  const renderItem = (appointment) => (
    <Card key={appointment.id}>
      <h3>{appointment.patient}</h3>
      <p>{appointment.date}</p>
    </Card>
  );

  return (
    <AnimatedList
      items={appointments}
      renderItem={renderItem}
      animationType="tableRow"
    />
  );
}
```

### Утилиты

```jsx
import { 
  useDebounce, 
  useLocalStorage, 
  useClipboard, 
  useDateUtils,
  useNumberUtils 
} from './design-system';

function UtilsExample() {
  const [searchQuery, setSearchQuery] = useState('');
  const debouncedQuery = useDebounce(searchQuery, 500);
  
  const [userPreferences, setUserPreferences] = useLocalStorage('userPrefs', {});
  const { copied, copyToClipboard } = useClipboard();
  const { formatDate, getRelativeTime } = useDateUtils();
  const { formatCurrency, formatPercentage } = useNumberUtils();

  const handleCopy = () => {
    copyToClipboard('Текст для копирования');
  };

  return (
    <div>
      <input
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
        placeholder="Поиск..."
      />
      
      <p>Отложенный запрос: {debouncedQuery}</p>
      
      <Button onClick={handleCopy}>
        {copied ? 'Скопировано!' : 'Копировать'}
      </Button>
      
      <p>Дата: {formatDate(new Date())}</p>
      <p>Относительное время: {getRelativeTime(new Date())}</p>
      <p>Валюта: {formatCurrency(150000)}</p>
      <p>Процент: {formatPercentage(85.5)}</p>
    </div>
  );
}
```

## 🎨 Кастомизация

### Создание собственных компонентов

```jsx
import { useTheme, cn } from './design-system';

function CustomButton({ children, variant = 'primary', size = 'md', ...props }) {
  const { getColor, getSpacing, getFontSize } = useTheme();

  const variants = {
    primary: { bg: getColor('primary.500'), color: 'white' },
    secondary: { bg: getColor('gray.200'), color: getColor('gray.800') },
    medical: { bg: getColor('medical.success'), color: 'white' }
  };

  const sizes = {
    sm: { padding: getSpacing('sm'), fontSize: getFontSize('sm') },
    md: { padding: getSpacing('md'), fontSize: getFontSize('base') },
    lg: { padding: getSpacing('lg'), fontSize: getFontSize('lg') }
  };

  const style = {
    ...variants[variant],
    ...sizes[size],
    border: 'none',
    borderRadius: '8px',
    cursor: 'pointer',
    transition: 'all 0.2s ease'
  };

  return (
    <button
      className={cn('custom-button', props.className)}
      style={style}
      {...props}
    >
      {children}
    </button>
  );
}
```

### Расширение темы

```jsx
import { ThemeProvider } from './design-system';

const customTheme = {
  colors: {
    brand: {
      50: '#f0f9ff',
      500: '#3b82f6',
      900: '#1e3a8a'
    }
  },
  spacing: {
    xs: '4px',
    sm: '8px',
    md: '16px',
    lg: '24px',
    xl: '32px'
  }
};

function App() {
  return (
    <ThemeProvider theme={customTheme}>
      <MainContent />
    </ThemeProvider>
  );
}
```

## 📱 Адаптивность

### Мобильная оптимизация

```jsx
import { useBreakpoint, useDevice } from './design-system';

function ResponsiveLayout() {
  const { isMobile, isTablet, isDesktop } = useBreakpoint();
  const { device } = useDevice();

  if (isMobile) {
    return <MobileLayout />;
  }

  if (isTablet) {
    return <TabletLayout />;
  }

  return <DesktopLayout />;
}
```

### Touch-оптимизация

```jsx
import { useTouchDevice, useHoverSupport } from './design-system';

function TouchOptimizedButton() {
  const { isTouchDevice } = useTouchDevice();
  const { hasHoverSupport } = useHoverSupport();

  const buttonStyle = {
    padding: isTouchDevice ? '16px' : '12px',
    minHeight: isTouchDevice ? '44px' : '36px',
    cursor: hasHoverSupport ? 'pointer' : 'default'
  };

  return (
    <Button style={buttonStyle}>
      Touch-оптимизированная кнопка
    </Button>
  );
}
```

## ♿ Доступность

### ARIA-атрибуты

```jsx
import { Button, Card } from './design-system';

function AccessibleComponent() {
  return (
    <Card>
      <h2 id="appointments-heading">Записи на сегодня</h2>
      
      <Button
        aria-describedby="appointments-heading"
        aria-label="Создать новую запись"
        role="button"
      >
        Создать запись
      </Button>
    </Card>
  );
}
```

### Клавиатурная навигация

```jsx
import { useKeyPress, useKeyCombo } from './design-system';

function KeyboardNavigation() {
  useKeyPress('Escape', () => {
    console.log('Нажата клавиша Escape');
  });

  useKeyCombo(['Ctrl', 's'], () => {
    console.log('Нажата комбинация Ctrl+S');
  });

  return <div>Компонент с клавиатурной навигацией</div>;
}
```

## 🚀 Производительность

### Мемоизация

```jsx
import { useMemoizedCallback, useMemoizedValue } from './design-system';

function OptimizedComponent({ data, onUpdate }) {
  const memoizedCallback = useMemoizedCallback(onUpdate, [data]);
  const memoizedValue = useMemoizedValue(data.filter(item => item.active), [data]);

  return (
    <div>
      {memoizedValue.map(item => (
        <div key={item.id} onClick={() => memoizedCallback(item.id)}>
          {item.name}
        </div>
      ))}
    </div>
  );
}
```

### Виртуализация

```jsx
import { useVirtualization } from './design-system';

function VirtualizedList({ items, itemHeight = 50 }) {
  const { visibleItems, containerHeight, scrollTop } = useVirtualization({
    items,
    itemHeight,
    containerHeight: 400
  });

  return (
    <div style={{ height: containerHeight, overflow: 'auto' }}>
      <div style={{ height: items.length * itemHeight, position: 'relative' }}>
        {visibleItems.map((item, index) => (
          <div
            key={item.id}
            style={{
              position: 'absolute',
              top: (item.index * itemHeight) - scrollTop,
              height: itemHeight,
              width: '100%'
            }}
          >
            {item.data.name}
          </div>
        ))}
      </div>
    </div>
  );
}
```

## 🧪 Тестирование

### Тестирование компонентов

```jsx
import { render, screen } from '@testing-library/react';
import { Button, ThemeProvider } from './design-system';

test('Button renders correctly', () => {
  render(
    <ThemeProvider>
      <Button variant="primary">Test Button</Button>
    </ThemeProvider>
  );

  expect(screen.getByRole('button')).toBeInTheDocument();
  expect(screen.getByText('Test Button')).toBeInTheDocument();
});
```

### Тестирование хуков

```jsx
import { renderHook } from '@testing-library/react';
import { useTheme } from './design-system';

test('useTheme returns theme values', () => {
  const { result } = renderHook(() => useTheme());

  expect(result.current.theme).toBeDefined();
  expect(result.current.getColor).toBeInstanceOf(Function);
  expect(result.current.getSpacing).toBeInstanceOf(Function);
});
```

## 📚 Дополнительные ресурсы

- [Документация по доступности](https://www.w3.org/WAI/WCAG21/quickref/)
- [Медицинские стандарты UX](https://www.himss.org/resources/healthcare-ux-design)
- [React документация](https://reactjs.org/docs/getting-started.html)
- [Tailwind CSS](https://tailwindcss.com/docs)

## 🤝 Вклад в проект

1. Форкните репозиторий
2. Создайте ветку для новой функции
3. Внесите изменения
4. Добавьте тесты
5. Создайте Pull Request

## 📄 Лицензия

MIT License - см. файл [LICENSE](LICENSE) для деталей.

---

**Создано с ❤️ для медицинских интерфейсов**