/**
 * Система тем для медицинской системы
 * Поддержка светлой и темной темы
 */

import { tokens } from './tokens';

// Светлая тема
export const lightTheme = {
  name: 'light',
  
  colors: {
    // Основные цвета остаются теми же
    primary: tokens.colors.primary,
    medical: tokens.colors.medical,
    gray: tokens.colors.gray,
    
    // Семантические цвета для светлой темы
    background: {
      primary: '#ffffff',
      secondary: '#f9fafb',
      tertiary: '#f3f4f6',
      elevated: '#ffffff',
      overlay: 'rgba(0, 0, 0, 0.5)',
      disabled: '#f3f4f6'
    },
    
    text: {
      primary: '#111827',
      secondary: '#4b5563',
      tertiary: '#9ca3af',
      inverse: '#ffffff',
      disabled: '#9ca3af'
    },
    
    border: {
      light: '#e5e7eb',
      medium: '#d1d5db',
      dark: '#9ca3af',
      focus: tokens.colors.primary[500]
    },
    
    surface: {
      card: '#ffffff',
      input: '#ffffff',
      button: '#ffffff',
      hover: '#f9fafb',
      active: '#f3f4f6',
      selected: '#e0f2fe'
    },
    
    status: {
      success: tokens.colors.medical.success,
      warning: tokens.colors.medical.warning,
      danger: tokens.colors.medical.danger,
      info: tokens.colors.medical.info
    }
  },
  
  shadows: {
    ...tokens.shadows,
    card: tokens.shadows.base,
    modal: tokens.shadows.xl,
    dropdown: tokens.shadows.lg
  }
};

// Темная тема
export const darkTheme = {
  name: 'dark',
  
  colors: {
    // Основные цвета остаются теми же
    primary: tokens.colors.primary,
    medical: tokens.colors.medical,
    gray: tokens.colors.gray,
    
    // Семантические цвета для темной темы
    background: {
      primary: '#111827',
      secondary: '#1f2937',
      tertiary: '#374151',
      elevated: '#1f2937',
      overlay: 'rgba(0, 0, 0, 0.7)',
      disabled: '#374151'
    },
    
    text: {
      primary: '#f9fafb',
      secondary: '#d1d5db',
      tertiary: '#9ca3af',
      inverse: '#111827',
      disabled: '#6b7280'
    },
    
    border: {
      light: '#374151',
      medium: '#4b5563',
      dark: '#6b7280',
      focus: tokens.colors.primary[400]
    },
    
    surface: {
      card: '#1f2937',
      input: '#374151',
      button: '#374151',
      hover: '#374151',
      active: '#4b5563',
      selected: '#1e3a8a'
    },
    
    status: {
      success: '#10b981',
      warning: '#f59e0b',
      danger: '#ef4444',
      info: '#60a5fa'
    }
  },
  
  shadows: {
    ...tokens.shadows,
    card: '0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -1px rgba(0, 0, 0, 0.2)',
    modal: '0 20px 25px -5px rgba(0, 0, 0, 0.4), 0 10px 10px -5px rgba(0, 0, 0, 0.2)',
    dropdown: '0 10px 15px -3px rgba(0, 0, 0, 0.3), 0 4px 6px -2px rgba(0, 0, 0, 0.2)'
  }
};

// Функция для получения темы по имени
export const getTheme = (themeName = 'light') => {
  switch (themeName) {
    case 'dark':
      return darkTheme;
    case 'light':
    default:
      return lightTheme;
  }
};

// CSS переменные для темы
export const generateCSSVariables = (theme) => {
  const cssVars = {};
  
  // Цвета
  Object.entries(theme.colors).forEach(([category, colors]) => {
    if (typeof colors === 'object' && colors !== null) {
      Object.entries(colors).forEach(([key, value]) => {
        if (typeof value === 'string') {
          cssVars[`--color-${category}-${key}`] = value;
        } else if (typeof value === 'object') {
          Object.entries(value).forEach(([subKey, subValue]) => {
            cssVars[`--color-${category}-${key}-${subKey}`] = subValue;
          });
        }
      });
    }
  });
  
  // Тени
  Object.entries(theme.shadows).forEach(([key, value]) => {
    cssVars[`--shadow-${key}`] = value;
  });
  
  // Токены дизайна
  Object.entries(tokens.spacing).forEach(([key, value]) => {
    cssVars[`--spacing-${key}`] = value;
  });
  
  Object.entries(tokens.borderRadius).forEach(([key, value]) => {
    cssVars[`--radius-${key}`] = value;
  });
  
  Object.entries(tokens.typography.fontSize).forEach(([key, value]) => {
    cssVars[`--font-size-${key}`] = value;
  });
  
  Object.entries(tokens.typography.fontWeight).forEach(([key, value]) => {
    cssVars[`--font-weight-${key}`] = value;
  });
  
  Object.entries(tokens.animation.duration).forEach(([key, value]) => {
    cssVars[`--duration-${key}`] = value;
  });
  
  Object.entries(tokens.zIndex).forEach(([key, value]) => {
    cssVars[`--z-${key}`] = value;
  });
  
  return cssVars;
};

// Применение CSS переменных к документу
export const applyCSSVariables = (theme) => {
  const cssVars = generateCSSVariables(theme);
  const root = document.documentElement;
  
  Object.entries(cssVars).forEach(([property, value]) => {
    root.style.setProperty(property, value);
  });
};

// Медиа-запросы для адаптивности
export const mediaQueries = {
  sm: `@media (min-width: ${tokens.breakpoints.sm})`,
  md: `@media (min-width: ${tokens.breakpoints.md})`,
  lg: `@media (min-width: ${tokens.breakpoints.lg})`,
  xl: `@media (min-width: ${tokens.breakpoints.xl})`,
  '2xl': `@media (min-width: ${tokens.breakpoints['2xl']})`,
  
  // Специальные медиа-запросы
  mobile: `@media (max-width: ${tokens.breakpoints.md})`,
  tablet: `@media (min-width: ${tokens.breakpoints.md}) and (max-width: ${tokens.breakpoints.lg})`,
  desktop: `@media (min-width: ${tokens.breakpoints.lg})`,
  
  // Предпочтения пользователя
  prefersReducedMotion: '@media (prefers-reduced-motion: reduce)',
  prefersDarkScheme: '@media (prefers-color-scheme: dark)',
  prefersLightScheme: '@media (prefers-color-scheme: light)'
};

export { lightTheme as defaultTheme };


