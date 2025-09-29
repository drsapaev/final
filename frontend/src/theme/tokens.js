/**
 * Токены дизайна для медицинской системы
 * Централизованная система цветов, размеров, типографики
 */

// Цветовая палитра
export const colors = {
  // Основные цвета
  primary: {
    50: '#f0f9ff',
    100: '#e0f2fe',
    200: '#bae6fd',
    300: '#7dd3fc',
    400: '#38bdf8',
    500: '#0ea5e9', // Основной синий
    600: '#0284c7',
    700: '#0369a1',
    800: '#075985',
    900: '#0c4a6e'
  },
  
  // Медицинские цвета
  medical: {
    success: '#10b981', // Зеленый для успеха
    warning: '#f59e0b', // Оранжевый для предупреждений
    danger: '#ef4444',  // Красный для опасности
    info: '#3b82f6',    // Синий для информации
    cardiology: '#dc2626', // Красный для кардиологии
    dermatology: '#7c3aed', // Фиолетовый для дерматологии
    dentistry: '#059669',   // Зеленый для стоматологии
    laboratory: '#0891b2', // Голубой для лаборатории
    ecg: '#ea580c'         // Оранжевый для ЭКГ
  },
  
  // Нейтральные цвета
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
  
  // Семантические цвета
  semantic: {
    background: {
      primary: '#ffffff',
      secondary: '#f9fafb',
      tertiary: '#f3f4f6'
    },
    text: {
      primary: '#111827',
      secondary: '#4b5563',
      tertiary: '#9ca3af',
      inverse: '#ffffff'
    },
    border: {
      light: '#e5e7eb',
      medium: '#d1d5db',
      dark: '#9ca3af'
    },
    surface: {
      elevated: '#ffffff',
      overlay: 'rgba(0, 0, 0, 0.5)',
      disabled: '#f3f4f6'
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

// Медицинские специфичные токены
export const medical = {
  // Статусы пациентов
  patientStatus: {
    waiting: colors.medical.warning,
    inProgress: colors.medical.info,
    completed: colors.medical.success,
    cancelled: colors.gray[400],
    emergency: colors.medical.danger
  },
  
  // Приоритеты
  priority: {
    low: colors.gray[400],
    normal: colors.medical.info,
    high: colors.medical.warning,
    urgent: colors.medical.danger,
    emergency: colors.medical.danger
  },
  
  // Отделения
  departments: {
    cardiology: colors.medical.cardiology,
    dermatology: colors.medical.dermatology,
    dentistry: colors.medical.dentistry,
    laboratory: colors.medical.laboratory,
    ecg: colors.medical.ecg,
    general: colors.primary[500]
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


