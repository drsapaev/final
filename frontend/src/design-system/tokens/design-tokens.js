/**
 * Единая система дизайн-токенов для медицинской клиники
 * Основана на принципах Material Design 3 и медицинских стандартах UX
 */

export const designTokens = {
  // Цветовая палитра
  colors: {
    // Основные цвета
    primary: {
      50: '#e6f2ff',
      100: '#b3d9ff',
      200: '#80bfff',
      300: '#4da6ff',
      400: '#1a8cff',
      500: '#0066cc', // Основной синий
      600: '#0052a3',
      700: '#003d7a',
      800: '#002952',
      900: '#001429'
    },
    
    // Медицинские цвета
    medical: {
      success: '#10b981',    // Зеленый для успеха
      warning: '#f59e0b',    // Оранжевый для предупреждений
      danger: '#ef4444',     // Красный для опасности
      info: '#06b6d4',       // Голубой для информации
      emergency: '#dc2626',  // Красный для экстренных случаев
      pending: '#8b5cf6',   // Фиолетовый для ожидания
      completed: '#059669'   // Темно-зеленый для завершенных
    },
    
    // Семантические цвета
    semantic: {
      background: {
        primary: '#ffffff',
        secondary: '#f8fafc',
        tertiary: '#f1f5f9',
        elevated: '#ffffff'
      },
      surface: {
        primary: '#ffffff',
        secondary: '#f8fafc',
        tertiary: '#f1f5f9',
        hover: '#f1f5f9'
      },
      text: {
        primary: '#1e293b',
        secondary: '#64748b',
        tertiary: '#94a3b8',
        disabled: '#cbd5e1',
        inverse: '#ffffff'
      },
      border: {
        primary: '#e2e8f0',
        secondary: '#cbd5e1',
        focus: '#3b82f6',
        error: '#ef4444'
      }
    },
    
    // Темная тема
    dark: {
      background: {
        primary: '#0f172a',
        secondary: '#1e293b',
        tertiary: '#334155',
        elevated: '#1e293b'
      },
      surface: {
        primary: '#1e293b',
        secondary: '#334155',
        tertiary: '#475569',
        hover: '#334155'
      },
      text: {
        primary: '#f8fafc',
        secondary: '#94a3b8',
        tertiary: '#64748b',
        disabled: '#475569',
        inverse: '#0f172a'
      },
      border: {
        primary: '#334155',
        secondary: '#475569',
        focus: '#60a5fa',
        error: '#f87171'
      }
    }
  },
  
  // Типографика
  typography: {
    fontFamily: {
      primary: '"Inter", "Segoe UI", "Roboto", sans-serif',
      secondary: '"JetBrains Mono", "Fira Code", monospace',
      medical: '"Roboto", "Arial", sans-serif'
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
      light: 300,
      normal: 400,
      medium: 500,
      semibold: 600,
      bold: 700,
      extrabold: 800
    },
    lineHeight: {
      tight: 1.25,
      normal: 1.5,
      relaxed: 1.75
    }
  },
  
  // Отступы и размеры
  spacing: {
    xs: '4px',
    sm: '8px',
    md: '16px',
    lg: '24px',
    xl: '32px',
    '2xl': '48px',
    '3xl': '64px',
    '4xl': '96px'
  },
  
  // Радиусы скругления
  borderRadius: {
    none: '0',
    sm: '4px',
    md: '8px',
    lg: '12px',
    xl: '16px',
    '2xl': '24px',
    full: '9999px'
  },
  
  // Тени
  boxShadow: {
    sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
    md: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
    lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
    xl: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
    '2xl': '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
    inner: 'inset 0 2px 4px 0 rgba(0, 0, 0, 0.06)'
  },
  
  // Анимации
  animation: {
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
  },
  
  // Брейкпоинты
  breakpoints: {
    xs: '360px',
    sm: '640px',
    md: '768px',
    lg: '1024px',
    xl: '1280px',
    '2xl': '1536px'
  },
  
  // Z-индексы
  zIndex: {
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
  }
};

// Утилиты для работы с токенами
export const getToken = (path) => {
  const keys = path.split('.');
  let value = designTokens;
  
  for (const key of keys) {
    value = value?.[key];
    if (value === undefined) return undefined;
  }
  
  return value;
};

export const getColor = (path, theme = 'light') => {
  if (theme === 'dark' && path.startsWith('semantic.')) {
    const darkPath = path.replace('semantic.', 'dark.');
    return getToken(darkPath) || getToken(path);
  }
  return getToken(`colors.${path}`);
};

export const getSpacing = (size) => getToken(`spacing.${size}`);
export const getFontSize = (size) => getToken(`typography.fontSize.${size}`);
export const getFontWeight = (weight) => getToken(`typography.fontWeight.${weight}`);
export const getBorderRadius = (size) => getToken(`borderRadius.${size}`);
export const getShadow = (size) => getToken(`boxShadow.${size}`);
export const getBreakpoint = (size) => getToken(`breakpoints.${size}`);

export default designTokens;
