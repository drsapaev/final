/**
 * Улучшенная система темизации с поддержкой системных цветовых схем
 * Интеграция с медицинскими стандартами и доступностью
 */

import React, { createContext, useContext, useState, useEffect } from 'react';
import { designTokens, getColor, getToken } from '../tokens/design-tokens';

const ThemeContext = createContext();

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};

export const ThemeProvider = ({ children }) => {
  const [theme, setThemeState] = useState(() => {
    // Проверяем сохранённую тему
    const saved = localStorage.getItem('ui_theme') || localStorage.getItem('theme');
    if (saved && (saved === 'light' || saved === 'dark' || saved === 'auto')) {
      return saved;
    }
    
    // Проверяем системную тему
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark';
    }
    
    return 'light';
  });

  const [systemTheme, setSystemTheme] = useState(() => {
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark';
    }
    return 'light';
  });

  const isDark = theme === 'dark' || (theme === 'auto' && systemTheme === 'dark');
  const isLight = theme === 'light' || (theme === 'auto' && systemTheme === 'light');
  
  // Медицинские цветовые схемы
  const medicalSchemes = {
    cardiology: {
      primary: '#dc2626',    // Красный для кардиологии
      secondary: '#fef2f2',
      accent: '#fca5a5'
    },
    dermatology: {
      primary: '#059669',   // Зеленый для дерматологии
      secondary: '#ecfdf5',
      accent: '#6ee7b7'
    },
    dentistry: {
      primary: '#7c3aed',   // Фиолетовый для стоматологии
      secondary: '#f3e8ff',
      accent: '#c4b5fd'
    },
    laboratory: {
      primary: '#0891b2',   // Голубой для лаборатории
      secondary: '#f0f9ff',
      accent: '#7dd3fc'
    }
  };

  // Утилитарные функции для работы с токенами
  const getThemeColor = (color, shade = 500) => {
    if (color === 'primary' || color === 'secondary') {
      return getToken(`colors.${color}.${shade}`) || getToken('colors.primary.500');
    } else if (color === 'success' || color === 'warning' || color === 'danger' || color === 'info') {
      return getToken(`colors.medical.${color}`) || getToken('colors.primary.500');
    } else if (color === 'text' || color === 'background' || color === 'border' || color === 'surface') {
      const themeKey = isDark ? 'dark' : 'semantic';
      return getToken(`colors.${themeKey}.${color}.primary`) || '#ffffff';
    }
    return getToken('colors.primary.500');
  };

  const getSpacing = (size) => {
    return getToken(`spacing.${size}`) || getToken('spacing.md') || '16px';
  };

  const getFontSize = (size) => {
    return getToken(`typography.fontSize.${size}`) || getToken('typography.fontSize.base') || '16px';
  };

  const getFontWeight = (weight) => {
    return getToken(`typography.fontWeight.${weight}`) || getToken('typography.fontWeight.normal') || '400';
  };

  const getBorderRadius = (size) => {
    return getToken(`borderRadius.${size}`) || getToken('borderRadius.md') || '8px';
  };

  const getShadow = (size) => {
    return getToken(`boxShadow.${size}`) || getToken('boxShadow.md') || '0 4px 6px -1px rgba(0, 0, 0, 0.1)';
  };

  const getBreakpoint = (size) => {
    return getToken(`breakpoints.${size}`) || '768px';
  };

  const setTheme = (newTheme) => {
    if (newTheme === 'light' || newTheme === 'dark' || newTheme === 'auto') {
      setThemeState(newTheme);
      localStorage.setItem('ui_theme', newTheme);
      localStorage.setItem('theme', newTheme); // Backward compatibility
    }
  };

  const toggleTheme = () => {
    const newTheme = isDark ? 'light' : 'dark';
    setTheme(newTheme);
  };

  // Применение CSS переменных и классов
  useEffect(() => {
    // Сохраняем тему
    localStorage.setItem('ui_theme', theme);
    localStorage.setItem('theme', theme);
    
    // Применяем CSS классы к body и document
    document.body.classList.remove('light-theme', 'dark-theme', 'auto-theme');
    document.body.classList.add(`${theme}-theme`);
    document.documentElement.setAttribute('data-theme', theme);
    
    // Устанавливаем CSS переменные из design-system
    const root = document.documentElement;
    
    if (isDark) {
      // Темная тема
      root.style.setProperty('--bg-primary', getToken('colors.dark.background.primary'));
      root.style.setProperty('--bg-secondary', getToken('colors.dark.background.secondary'));
      root.style.setProperty('--bg-tertiary', getToken('colors.dark.background.tertiary'));
      root.style.setProperty('--text-primary', getToken('colors.dark.text.primary'));
      root.style.setProperty('--text-secondary', getToken('colors.dark.text.secondary'));
      root.style.setProperty('--text-tertiary', getToken('colors.dark.text.tertiary'));
      root.style.setProperty('--border-color', getToken('colors.dark.border.primary'));
      root.style.setProperty('--hover-bg', getToken('colors.dark.surface.hover'));
      root.style.setProperty('--accent-color', getToken('colors.primary.400'));
    } else {
      // Светлая тема
      root.style.setProperty('--bg-primary', getToken('colors.semantic.background.primary'));
      root.style.setProperty('--bg-secondary', getToken('colors.semantic.background.secondary'));
      root.style.setProperty('--bg-tertiary', getToken('colors.semantic.background.tertiary'));
      root.style.setProperty('--text-primary', getToken('colors.semantic.text.primary'));
      root.style.setProperty('--text-secondary', getToken('colors.semantic.text.secondary'));
      root.style.setProperty('--text-tertiary', getToken('colors.semantic.text.tertiary'));
      root.style.setProperty('--border-color', getToken('colors.semantic.border.primary'));
      root.style.setProperty('--hover-bg', getToken('colors.semantic.surface.hover'));
      root.style.setProperty('--accent-color', getToken('colors.primary.500'));
    }
    
    // Дополнительные переменные для статусов
    root.style.setProperty('--success-color', getToken('colors.medical.success'));
    root.style.setProperty('--warning-color', getToken('colors.medical.warning'));
    root.style.setProperty('--danger-color', getToken('colors.medical.danger'));
    root.style.setProperty('--info-color', getToken('colors.medical.info'));
    
    // Переменные для теней
    root.style.setProperty('--shadow-sm', getToken('boxShadow.sm'));
    root.style.setProperty('--shadow-md', getToken('boxShadow.md'));
    root.style.setProperty('--shadow-lg', getToken('boxShadow.lg'));
    root.style.setProperty('--shadow-xl', getToken('boxShadow.xl'));
    
    // Переменные для отступов
    root.style.setProperty('--spacing-xs', getToken('spacing.xs'));
    root.style.setProperty('--spacing-sm', getToken('spacing.sm'));
    root.style.setProperty('--spacing-md', getToken('spacing.md'));
    root.style.setProperty('--spacing-lg', getToken('spacing.lg'));
    root.style.setProperty('--spacing-xl', getToken('spacing.xl'));
    
    // Переменные для размеров шрифтов
    root.style.setProperty('--font-size-xs', getToken('typography.fontSize.xs'));
    root.style.setProperty('--font-size-sm', getToken('typography.fontSize.sm'));
    root.style.setProperty('--font-size-base', getToken('typography.fontSize.base'));
    root.style.setProperty('--font-size-lg', getToken('typography.fontSize.lg'));
    root.style.setProperty('--font-size-xl', getToken('typography.fontSize.xl'));
    root.style.setProperty('--font-size-2xl', getToken('typography.fontSize.2xl'));
    root.style.setProperty('--font-size-3xl', getToken('typography.fontSize.3xl'));
    
  }, [theme, isDark, systemTheme]);

  // Слушаем изменения системной темы
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = (e) => {
      setSystemTheme(e.matches ? 'dark' : 'light');
      // Применяем системную тему только если нет сохраненной
      if (!localStorage.getItem('ui_theme') && !localStorage.getItem('theme')) {
        const newTheme = e.matches ? 'dark' : 'light';
        setThemeState(newTheme);
      }
    };

    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  const value = {
    theme,
    setTheme,
    toggleTheme,
    isDark,
    isLight,
    systemTheme,
    medicalSchemes,
    designTokens,
    getColor: getThemeColor,
    getSpacing,
    getFontSize,
    getFontWeight,
    getBorderRadius,
    getShadow,
    getBreakpoint
  };

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  );
};

export default ThemeProvider;
