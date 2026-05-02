# 🛠️ Гайдлайны для разработчиков

## 📋 Обзор

Этот документ содержит правила и рекомендации для разработки компонентов и панелей в нашем приложении с использованием дизайн-системы.

## 🎯 Принципы разработки

### 1. **Используйте дизайн-систему**
- Всегда импортируйте компоненты из `../design-system`
- Используйте токены для цветов, отступов, размеров
- Следуйте установленным паттернам

### 2. **Компонентный подход**
- Создавайте переиспользуемые компоненты
- Разделяйте логику и представление
- Используйте forwardRef для доступа к DOM

### 3. **Адаптивность**
- Всегда используйте responsive хуки
- Тестируйте на всех устройствах
- Следуйте mobile-first подходу

### 4. **Доступность**
- Добавляйте ARIA атрибуты
- Поддерживайте клавиатурную навигацию
- Обеспечивайте достаточный контраст

## 🧩 Создание компонентов

### **Структура компонента**

```javascript
import React, { forwardRef } from 'react';
import { designTokens, getColor, getSpacing } from '../design-system';
import { SIZES, VARIANTS } from '../design-system/components/types';

const MyComponent = forwardRef(({
  // Props с дефолтными значениями
  variant = VARIANTS.PRIMARY,
  size = SIZES.MD,
  disabled = false,
  className = '',
  style = {},
  children,
  ...props
}, ref) => {
  // Стили с использованием токенов
  const componentStyles = {
    // Базовые стили
    display: 'flex',
    alignItems: 'center',
    gap: getSpacing('sm'),
    
    // Размеры
    padding: size === SIZES.SM ? getSpacing('sm') : getSpacing('md'),
    fontSize: designTokens.typography.fontSize[size],
    
    // Цвета
    color: getColor('primary', 500),
    backgroundColor: getColor('primary', 50),
    
    // Анимации
    transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
    
    // Переданные стили
    ...style
  };

  return (
    <div
      ref={ref}
      className={`my-component ${className}`}
      style={componentStyles}
      {...props}
    >
      {children}
    </div>
  );
});

MyComponent.displayName = 'MyComponent';

export default MyComponent;
```

### **Обязательные правила**

1. **Используйте forwardRef** для всех компонентов
2. **Добавляйте displayName** для отладки
3. **Используйте токены** вместо хардкода
4. **Поддерживайте className** для кастомизации
5. **Добавляйте ...props** для дополнительных атрибутов

## 🎨 Стилизация

### **Использование токенов**

```javascript
import { designTokens, getColor, getSpacing, getFontSize } from '../design-system';

// ✅ Правильно
const styles = {
  color: getColor('primary', 500),
  padding: getSpacing('md'),
  fontSize: getFontSize('lg'),
  borderRadius: designTokens.borderRadius.lg
};

// ❌ Неправильно
const styles = {
  color: '#3b82f6',
  padding: '16px',
  fontSize: '18px',
  borderRadius: '12px'
};
```

### **Адаптивные стили**

```javascript
import { useBreakpoint } from '../design-system';

const MyComponent = () => {
  const { isMobile, isTablet } = useBreakpoint();
  
  const styles = {
    padding: isMobile ? getSpacing('sm') : getSpacing('md'),
    fontSize: isMobile ? getFontSize('sm') : getFontSize('base'),
    flexDirection: isMobile ? 'column' : 'row'
  };

  return <div style={styles}>...</div>;
};
```

### **Темы**

```javascript
import { useTheme } from '../design-system';

const MyComponent = () => {
  const { theme, themeConfig, toggleTheme } = useTheme();
  
  const styles = {
    backgroundColor: themeConfig.background,
    color: themeConfig.text,
    border: `1px solid ${themeConfig.border}`
  };

  return (
    <div style={styles}>
      <button onClick={toggleTheme}>
        Переключить тему
      </button>
    </div>
  );
};
```

## 🎭 Анимации

### **Использование AnimatedTransition**

```javascript
import { AnimatedTransition, ANIMATION_TYPES } from '../design-system';

const MyComponent = () => {
  return (
    <AnimatedTransition
      type={ANIMATION_TYPES.FADE}
      delay={100}
      duration={300}
    >
      <div>Анимированный контент</div>
    </AnimatedTransition>
  );
};
```

### **Создание кастомных анимаций**

```javascript
const styles = {
  transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
  transform: isHovered ? 'translateY(-2px)' : 'translateY(0)',
  boxShadow: isHovered 
    ? '0 8px 25px rgba(0, 0, 0, 0.15)' 
    : '0 2px 8px rgba(0, 0, 0, 0.1)'
};
```

## 📱 Адаптивность

### **Breakpoints**

```javascript
import { useBreakpoint } from '../design-system';

const { isMobile, isTablet, isDesktop } = useBreakpoint();

// Условная логика
if (isMobile) {
  // Мобильная версия
} else if (isTablet) {
  // Планшетная версия
} else {
  // Десктопная версия
}
```

### **Touch устройства**

```javascript
import { useTouchDevice } from '../design-system';

const isTouch = useTouchDevice();

const styles = {
  // Увеличиваем размеры для touch
  minHeight: isTouch ? '44px' : '32px',
  minWidth: isTouch ? '44px' : '32px'
};
```

## 🧪 Тестирование

### **Обязательные тесты**

1. **Визуальные тесты** - проверка внешнего вида
2. **Функциональные тесты** - проверка поведения
3. **Адаптивные тесты** - проверка на всех устройствах
4. **Accessibility тесты** - проверка доступности

### **Пример теста**

```javascript
import { render, screen } from '@testing-library/react';
import { Button } from '../design-system';

test('Button renders with correct text', () => {
  render(<Button>Click me</Button>);
  expect(screen.getByText('Click me')).toBeInTheDocument();
});

test('Button is disabled when disabled prop is true', () => {
  render(<Button disabled>Click me</Button>);
  expect(screen.getByRole('button')).toBeDisabled();
});
```

## 📝 Документация

### **Обязательная документация**

1. **Props** - описание всех пропсов
2. **Examples** - примеры использования
3. **Accessibility** - требования доступности
4. **Testing** - инструкции по тестированию

### **Пример документации**

```javascript
/**
 * Button component for actions and interactions
 * 
 * @param {string} variant - Button variant (primary, secondary, success, danger, warning, info, ghost)
 * @param {string} size - Button size (sm, md, lg)
 * @param {boolean} disabled - Whether button is disabled
 * @param {boolean} loading - Whether button is in loading state
 * @param {boolean} fullWidth - Whether button takes full width
 * @param {string} className - Additional CSS class
 * @param {object} style - Additional inline styles
 * @param {function} onClick - Click handler
 * @param {React.ReactNode} children - Button content
 * 
 * @example
 * <Button variant="primary" size="md" onClick={handleClick}>
 *   Click me
 * </Button>
 * 
 * @accessibility
 * - Supports keyboard navigation
 * - Has proper ARIA attributes
 * - Provides visual feedback
 */
```

## 🚀 Производительность

### **Оптимизация**

1. **Используйте React.memo** для предотвращения лишних рендеров
2. **Используйте useCallback** для функций
3. **Используйте useMemo** для вычислений
4. **Избегайте inline объектов** в JSX

### **Пример оптимизации**

```javascript
import React, { memo, useCallback, useMemo } from 'react';

const MyComponent = memo(({ items, onItemClick }) => {
  const sortedItems = useMemo(() => {
    return items.sort((a, b) => a.name.localeCompare(b.name));
  }, [items]);

  const handleClick = useCallback((item) => {
    onItemClick(item);
  }, [onItemClick]);

  return (
    <div>
      {sortedItems.map(item => (
        <div key={item.id} onClick={() => handleClick(item)}>
          {item.name}
        </div>
      ))}
    </div>
  );
});
```

## 🔍 Code Review

### **Чек-лист для ревью**

- [ ] Использует дизайн-систему
- [ ] Поддерживает адаптивность
- [ ] Имеет анимации
- [ ] Доступен для всех пользователей
- [ ] Оптимизирован для производительности
- [ ] Имеет тесты
- [ ] Документирован
- [ ] Следует принципам дизайна

### **Критерии качества**

1. **Функциональность** - работает как ожидается
2. **Производительность** - быстрый и отзывчивый
3. **Доступность** - доступен для всех пользователей
4. **Адаптивность** - работает на всех устройствах
5. **Консистентность** - соответствует дизайн-системе

## 📚 Ресурсы

### **Документация**
- [Дизайн-система](./src/design-system/README.md)
- [План разработки](./DEVELOPMENT_PLAN.md)
- [Компоненты](./src/design-system/components/)

### **Инструменты**
- [Storybook](https://storybook.js.org/) - документация компонентов
- [React Testing Library](https://testing-library.com/docs/react-testing-library/intro/) - тестирование
- [Lighthouse](https://developers.google.com/web/tools/lighthouse) - аудит производительности

### **Стандарты**
- [WCAG 2.1](https://www.w3.org/WAI/WCAG21/quickref/) - доступность
- [Material Design](https://material.io/design) - принципы дизайна
- [React Best Practices](https://react.dev/learn) - лучшие практики React

---

**Последнее обновление**: $(date)
**Версия**: 1.0.0
