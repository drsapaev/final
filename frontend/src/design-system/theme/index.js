/**
 * Главный файл темы дизайн-системы
 * Объединяет все элементы темы
 */
import colors from './colors.js';
import typography from './typography.js';
import spacing from './spacing.js';
import breakpoints from './breakpoints.js';

// Объединенная тема
export const theme = {
  colors,
  typography,
  spacing,
  breakpoints,
  
  // Тени
  shadows: {
    none: 'none',
    sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
    base: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
    md: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
    lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
    xl: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
    '2xl': '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
    inner: 'inset 0 2px 4px 0 rgba(0, 0, 0, 0.06)',
  },
  
  // Радиусы скругления
  borderRadius: {
    none: '0',
    sm: '0.125rem',
    base: '0.25rem',
    md: '0.375rem',
    lg: '0.5rem',
    xl: '0.75rem',
    '2xl': '1rem',
    '3xl': '1.5rem',
    full: '9999px',
  },
  
  // Переходы и анимации
  transitions: {
    duration: {
      fast: '150ms',
      base: '200ms',
      slow: '300ms',
      slower: '500ms',
    },
    
    easing: {
      linear: 'linear',
      ease: 'ease',
      easeIn: 'ease-in',
      easeOut: 'ease-out',
      easeInOut: 'ease-in-out',
      
      // Кастомные easing для медицинских интерфейсов
      medical: 'cubic-bezier(0.4, 0, 0.2, 1)',
      smooth: 'cubic-bezier(0.25, 0.46, 0.45, 0.94)',
    },
  },
  
  // Z-index слои
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
    tooltip: 1800,
  },
};

// Светлая тема
export const lightTheme = {
  ...theme,
  mode: 'light',
  colors: {
    ...theme.colors,
    background: theme.colors.light.background,
    text: theme.colors.light.text,
    divider: theme.colors.light.divider,
    action: theme.colors.light.action,
  },
};

// Темная тема
export const darkTheme = {
  ...theme,
  mode: 'dark',
  colors: {
    ...theme.colors,
    background: theme.colors.dark.background,
    text: theme.colors.dark.text,
    divider: theme.colors.dark.divider,
    action: theme.colors.dark.action,
  },
};

// Утилиты темы
export const themeUtils = {
  /**
   * Получение текущей темы
   */
  getCurrentTheme(isDark = false) {
    return isDark ? darkTheme : lightTheme;
  },
  
  /**
   * Создание CSS переменных из темы
   */
  createCSSVariables(theme) {
    const cssVars = {};
    
    // Цвета
    Object.entries(theme.colors.brand.primary).forEach(([key, value]) => {
      cssVars[`--color-primary-${key}`] = value;
    });
    
    // Отступы
    Object.entries(theme.spacing.spacing).forEach(([key, value]) => {
      cssVars[`--spacing-${key}`] = value;
    });
    
    // Шрифты
    Object.entries(theme.typography.fontSizes).forEach(([key, value]) => {
      cssVars[`--font-size-${key}`] = value;
    });
    
    return cssVars;
  }
};

// Экспорт всего
export {
  colors,
  typography,
  spacing,
  breakpoints,
};

export default theme;
