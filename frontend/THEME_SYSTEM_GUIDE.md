# 🎨 Руководство по централизованной системе темизации

## 📋 Обзор

Проект использует **единую централизованную систему темизации**, которая предотвращает фрагментацию дизайна и обеспечивает консистентность во всех компонентах.

## 🏗️ Архитектура

```
📂 Система темизации
├── 🎯 contexts/ThemeContext.jsx     # Основной провайдер темы
├── 🎨 styles/theme.css              # Универсальные CSS переменные и стили
├── 🧩 design-system/                # Токены дизайна
└── 🔧 components/ThemeToggle.jsx    # Переключатель темы
```

## 🚀 Использование

### 1. Импорт темы в компоненте

```javascript
import { useTheme } from '../contexts/ThemeContext';

const MyComponent = () => {
  const { 
    theme,           // 'light' | 'dark'
    isDark,          // boolean
    isLight,         // boolean
    toggleTheme,     // () => void
    getColor,        // (color, shade) => string
    getSpacing,      // (size) => string
    getFontSize,     // (size) => string
    getShadow,       // (size) => string
    designTokens     // полный объект токенов
  } = useTheme();

  return (
    <div style={{
      background: isLight ? getColor('primary', 50) : getColor('secondary', 900),
      padding: getSpacing('lg'),
      fontSize: getFontSize('base'),
      boxShadow: getShadow('md')
    }}>
      Содержимое компонента
    </div>
  );
};
```

### 2. Использование CSS переменных

```css
/* В CSS файлах */
.my-component {
  background: var(--bg-primary);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-md);
}

/* Или использовать готовые классы */
.clinic-card {
  /* Автоматически адаптируется к теме */
}
```

### 3. Готовые утилитарные классы

```jsx
// Используйте готовые классы вместо инлайн стилей
<div className="clinic-page">           {/* Страница */}
  <div className="clinic-card">         {/* Карточка */}
    <div className="clinic-header">     {/* Заголовок */}
      <h1>Заголовок</h1>
    </div>
    <button className="clinic-button clinic-button-primary">
      Действие
    </button>
  </div>
</div>
```

## 🎯 Принципы

### ✅ ДЕЛАЙТЕ ТАК:

```javascript
// ✅ Используйте функции темы
const cardStyle = {
  background: isLight ? getColor('primary', 50) : getColor('secondary', 900),
  padding: getSpacing('lg')
};

// ✅ Используйте CSS переменные  
const inputStyle = {
  border: '1px solid var(--border-color)',
  background: 'var(--bg-primary)'
};

// ✅ Используйте готовые классы
<div className="clinic-card clinic-fade-in">
```

### ❌ НЕ ДЕЛАЙТЕ ТАК:

```javascript
// ❌ НЕ определяйте собственные designTokens
const designTokens = {
  primary: { 500: '#3b82f6' } // ПЛОХО!
};

// ❌ НЕ используйте хардкод цвета
const style = {
  background: '#3b82f6', // ПЛОХО!
  color: '#ffffff'       // ПЛОХО!
};

// ❌ НЕ определяйте собственные отступы
const spacing = { md: '16px' }; // ПЛОХО!
```

## 🔧 Доступные функции

### `getColor(color, shade)`
```javascript
getColor('primary', 500)     // #3b82f6
getColor('success', 600)     // #16a34a 
getColor('danger', 500)      // #ef4444
```

### `getSpacing(size)`
```javascript
getSpacing('xs')     // 4px
getSpacing('sm')     // 8px
getSpacing('md')     // 16px
getSpacing('lg')     // 24px
getSpacing('xl')     // 32px
```

### `getFontSize(size)`
```javascript
getFontSize('sm')     // 14px
getFontSize('base')   // 16px
getFontSize('lg')     // 18px
getFontSize('xl')     // 20px
```

### `getShadow(size)`
```javascript
getShadow('sm')      // Мягкая тень
getShadow('md')      // Средняя тень  
getShadow('lg')      // Большая тень
getShadow('xl')      // Очень большая тень
```

## 📚 Цветовая палитра

### Основные цвета
- **Primary**: Синий (#3b82f6) - основной бренд
- **Secondary**: Серый (#64748b) - вторичные элементы
- **Success**: Зеленый (#22c55e) - успешные действия
- **Warning**: Оранжевый (#f59e0b) - предупреждения  
- **Danger**: Красный (#ef4444) - ошибки и опасные действия
- **Info**: Голубой (#0ea5e9) - информационные сообщения

### Оттенки
Каждый цвет имеет оттенки от 50 (самый светлый) до 900 (самый темный).

## 🌓 Темы

### Светлая тема (по умолчанию)
- Фон: белый и светло-серые оттенки
- Текст: темный
- Акцент: primary[500]

### Темная тема
- Фон: темно-серые и черные оттенки  
- Текст: светлый
- Акцент: primary[400]

## 🛡️ Стабильность

**Эта система гарантирует:**
- ✅ Автоматическую поддержку новых тем
- ✅ Консистентность всех компонентов
- ✅ Простоту изменения цветов глобально
- ✅ Отсутствие дублирования кода
- ✅ Адаптивность для мобильных устройств

## 🚨 Важные правила

1. **НИКОГДА не создавайте собственные designTokens** в компонентах
2. **ВСЕГДА используйте** функции `getColor()`, `getSpacing()` и т.д.
3. **ПРЕДПОЧИТАЙТЕ** CSS переменные для статических стилей
4. **ИСПОЛЬЗУЙТЕ** готовые утилитарные классы `.clinic-*`
5. **ТЕСТИРУЙТЕ** компоненты в обеих темах

## 🔄 Миграция старых компонентов

Если видите хардкод стили:

```javascript
// ❌ Старый код
const style = {
  background: '#3b82f6',
  padding: '16px'
};

// ✅ Обновленный код  
const { getColor, getSpacing } = useTheme();
const style = {
  background: getColor('primary', 500),
  padding: getSpacing('md')
};
```

---
*Документ создан автоматически при унификации системы дизайна*
