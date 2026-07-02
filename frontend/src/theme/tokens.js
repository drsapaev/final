/**
 * Токены дизайна для медицинской системы
 * Централизованная система цветов, размеров, типографики
 */

// Цветовая палитра (ОБЪЕДИНЕННАЯ ИЗ ВСЕХ СИСТЕМ)
export const colors = {
  // Основные брендовые цвета (выбраны лучшие из основной темы)
  primary: {
    50: '#f0f9ff',
    100: '#e0f2fe',
    200: '#bae6fd',
    300: '#7dd3fc',
    400: '#38bdf8',
    500: '#0ea5e9', // ✅ Основной синий (из основной темы)
    600: '#0284c7',
    700: '#0369a1',
    800: '#075985',
    900: '#0c4a6e'
  },

  // Статусные цвета (оптимизированные для лучшего контраста)
  status: {
    success: '#10b981',    // ✅ Зеленый (из основной темы)
    warning: '#f59e0b',    // ✅ Оранжевый (из основной темы)
    danger: '#ef4444',     // ✅ Красный (из основной темы)
    info: '#3b82f6',       // ✅ Синий (из основной темы)
    pending: '#f59e0b',    // Оранжевый для ожидания
    completed: '#10b981',  // Зеленый для завершения
    cancelled: '#6b7280'   // Серый для отмены
  },

  // Медицинские цвета отделений (специфичные для каждой специализации)
  medical: {
    cardiology: '#dc2626',   // ✅ Красный для кардиологии (лучший контраст)
    dermatology: '#7c3aed',  // Фиолетовый для дерматологии
    dentistry: '#059669',    // Зеленый для стоматологии
    laboratory: '#0891b2',   // Голубой для лаборатории
    general: '#0ea5e9',      // Синий для общих врачей
    ecg: '#ea580c',          // Оранжевый для ЭКГ
    neurology: '#8b5cf6',    // Фиолетовый для неврологии
    gynecology: '#ec4899',   // Розовый для гинекологии
    pediatrics: '#f59e0b',   // Оранжевый для педиатрии
    surgery: '#7f1d1d',      // Темно-красный для хирургии
    psychiatry: '#6b21a8',   // Темно-фиолетовый для психиатрии
    radiology: '#374151'     // Серый для радиологии
  },

  // Семантические цвета для действий в медицинской сфере
  actions: {
    // Критические действия (красные тона)
    emergency: '#dc2626',      // Экстренные случаи
    critical: '#b91c1c',       // Критические состояния
    urgent: '#ea580c',         // Срочно

    // Диагностика (синие тона)
    diagnose: '#2563eb',       // Диагностика
    examine: '#3b82f6',        // Осмотр
    test: '#0ea5e9',          // Анализы/тесты

    // Лечение (зеленые тона)
    treat: '#059669',          // Лечение
    prescribe: '#10b981',      // Назначение
    monitor: '#34d399',        // Мониторинг

    // Администрирование (серые тона)
    approve: '#374151',        // Одобрение
    reject: '#6b7280',         // Отклонение
    pending: '#9ca3af'         // Ожидание
  },

  // Вторичные цвета (для акцентов и дополнительных элементов)
  secondary: {
    50: '#f8fafc',
    100: '#f1f5f9',
    200: '#e2e8f0',
    300: '#cbd5e1',
    400: '#94a3b8',
    500: '#64748b',
    600: '#475569',
    700: '#334155',
    800: '#1e293b',
    900: '#0f172a'
  },
  
  // Нейтральные цвета (улучшенные)
  gray: {
    50: '#f9fafb',
    100: '#f3f4f6',
    200: '#e5e7eb',
    300: '#d1d5db',
    400: '#9ca3af',
    500: '#6b7280',
    600: '#4b5563',
    700: '#374151',
    800: '#1f2937',
    900: '#111827'
  },

  // Семантические цвета (для фона, текста и поверхностей)
  semantic: {
    background: {
      primary: '#ffffff',      // Основной фон
      secondary: '#f8fafc',    // Вторичный фон
      tertiary: '#f1f5f9',     // Третичный фон
      elevated: '#ffffff',     // Приподнятые элементы
      overlay: 'rgba(0, 0, 0, 0.5)', // Оверлеи
      disabled: '#f3f4f6'      // Отключенные элементы
    },
    text: {
      primary: '#0f172a',      // Основной текст
      secondary: '#374151',    // Вторичный текст
      tertiary: '#6b7280',     // Третичный текст
      inverse: '#ffffff',      // Инверсный текст
      disabled: '#9ca3af'      // Отключенный текст
    },
    border: {
      light: '#e5e7eb',        // Светлая граница
      medium: '#d1d5db',       // Средняя граница
      dark: '#9ca3af',         // Темная граница
      focus: '#0ea5e9'         // Граница фокуса
    },
    surface: {
      card: '#ffffff',         // Карточки
      input: '#ffffff',        // Поля ввода
      button: '#ffffff',       // Кнопки
      hover: '#f8fafc',        // Hover состояние
      active: '#f1f5f9',       // Active состояние
      selected: '#e0f2fe'      // Выбранное состояние
    }
  }
};

// Размеры и отступы
export const spacing = {
  0: '0px',
  1: '4px',
  2: '8px',
  3: '12px',
  4: '16px',
  5: '20px',
  6: '24px',
  8: '32px',
  10: '40px',
  12: '48px',
  16: '64px',
  20: '80px',
  24: '96px',
  32: '128px'
};

// Типографика
export const typography = {
  fontFamily: {
    sans: ['-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', 'sans-serif'],
    mono: ['SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'Liberation Mono', 'Courier New', 'monospace']
  },
  
  fontSize: {
    xs: '12px',
    sm: '14px',
    base: '16px',
    lg: '18px',
    xl: '20px',
    '2xl': '24px',
    '3xl': '30px',
    '4xl': '36px',
    '5xl': '48px'
  },
  
  fontWeight: {
    light: '300',
    normal: '400',
    medium: '500',
    semibold: '600',
    bold: '700',
    extrabold: '800'
  },
  
  lineHeight: {
    tight: '1.25',
    snug: '1.375',
    normal: '1.5',
    relaxed: '1.625',
    loose: '2'
  }
};

// Тени
export const shadows = {
  sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
  base: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
  md: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
  lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
  xl: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
  '2xl': '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
  inner: 'inset 0 2px 4px 0 rgba(0, 0, 0, 0.06)'
};

// Радиусы скругления
export const borderRadius = {
  none: '0px',
  sm: '2px',
  base: '4px',
  md: '6px',
  lg: '8px',
  xl: '12px',
  '2xl': '16px',
  '3xl': '24px',
  full: '9999px'
};

// Анимации
export const animation = {
  duration: {
    fast: '150ms',
    normal: '300ms',
    slow: '500ms'
  },
  
  easing: {
    linear: 'linear',
    ease: 'ease',
    easeIn: 'ease-in',
    easeOut: 'ease-out',
    easeInOut: 'ease-in-out'
  }
};

// Точки останова для адаптивности
export const breakpoints = {
  sm: '640px',
  md: '768px',
  lg: '1024px',
  xl: '1280px',
  '2xl': '1536px'
};

// Z-индексы
export const zIndex = {
  hide: -1,
  auto: 'auto',
  base: 0,
  docked: 10,
  dropdown: 1000,
  sticky: 1100,
  banner: 1200,
  overlay: 1300,
  modal: 1400,
  popover: 1500,
  skipLink: 1600,
  toast: 1700,
  tooltip: 1800
};

// Медицинские специфичные токены (используют новую структуру цветов)
export const medical = {
  // Статусы пациентов
  patientStatus: {
    waiting: colors.status.pending,     // Ожидание
    inProgress: colors.status.info,     // В процессе
    completed: colors.status.completed, // Завершено
    cancelled: colors.status.cancelled, // Отменено
    emergency: colors.status.danger     // Экстренный случай
  },

  // Приоритеты
  priority: {
    low: colors.gray[400],              // Низкий
    normal: colors.status.info,         // Нормальный
    high: colors.status.warning,        // Высокий
    urgent: colors.status.danger,       // Срочный
    emergency: colors.status.danger     // Экстренный
  },

  // Отделения (специфичные цвета)
  departments: {
    cardiology: colors.medical.cardiology,   // Кардиология - красный
    dermatology: colors.medical.dermatology, // Дерматология - фиолетовый
    dentistry: colors.medical.dentistry,     // Стоматология - зеленый
    laboratory: colors.medical.laboratory,   // Лаборатория - голубой
    ecg: colors.medical.ecg,                 // ЭКГ - оранжевый
    general: colors.medical.general          // Общая практика - синий
  }
};

// Экспорт всех токенов
export const tokens = {
  colors,
  spacing,
  typography,
  shadows,
  borderRadius,
  animation,
  breakpoints,
  zIndex,
  medical
};

export default tokens;


