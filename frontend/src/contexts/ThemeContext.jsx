import React, { createContext, useContext, useState, useEffect } from 'react';
import { designTokens, themes } from '../design-system';

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
    if (saved && (saved === 'light' || saved === 'dark')) {
      return saved;
    }
    
    // Проверяем системную тему
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark';
    }
    
    return 'light';
  });

  const isDark = theme === 'dark';
  const isLight = theme === 'light';
  const themeConfig = themes[theme] || themes.light;

  // Утилитарные функции для работы с токенами
  const getColor = (color, shade = 500) => {
    return designTokens.colors[color]?.[shade] || designTokens.colors.primary[500];
  };

  const getSpacing = (size) => {
    return designTokens.spacing[size] || designTokens.spacing.md;
  };

  const getFontSize = (size) => {
    return designTokens.typography.fontSize[size] || designTokens.typography.fontSize.base;
  };

  const getShadow = (size) => {
    return designTokens.boxShadow[size] || designTokens.boxShadow.md;
  };

  const setTheme = (newTheme) => {
    if (newTheme === 'light' || newTheme === 'dark') {
      setThemeState(newTheme);
      localStorage.setItem('ui_theme', newTheme);
      localStorage.setItem('theme', newTheme); // Backward compatibility
    }
  };

  const toggleTheme = () => {
    const newTheme = isDark ? 'light' : 'dark';
    setTheme(newTheme);
  };

  useEffect(() => {
    // Сохраняем тему
    localStorage.setItem('ui_theme', theme);
    localStorage.setItem('theme', theme);
    
    // Применяем CSS классы к body и document
    document.body.classList.remove('light-theme', 'dark-theme');
    document.body.classList.add(`${theme}-theme`);
    document.documentElement.setAttribute('data-theme', theme);
    
    // Устанавливаем расширенные CSS переменные из design-system
    const root = document.documentElement;
    
    if (isDark) {
      // Темная тема
      root.style.setProperty('--bg-primary', designTokens.colors.secondary[900]);
      root.style.setProperty('--bg-secondary', designTokens.colors.secondary[800]);
      root.style.setProperty('--bg-tertiary', designTokens.colors.secondary[700]);
      root.style.setProperty('--text-primary', designTokens.colors.secondary[50]);
      root.style.setProperty('--text-secondary', designTokens.colors.secondary[300]);
      root.style.setProperty('--text-tertiary', designTokens.colors.secondary[400]);
      root.style.setProperty('--border-color', designTokens.colors.secondary[600]);
      root.style.setProperty('--hover-bg', designTokens.colors.secondary[700]);
      root.style.setProperty('--accent-color', designTokens.colors.primary[400]);
    } else {
      // Светлая тема
      root.style.setProperty('--bg-primary', '#ffffff');
      root.style.setProperty('--bg-secondary', designTokens.colors.secondary[50]);
      root.style.setProperty('--bg-tertiary', designTokens.colors.secondary[100]);
      root.style.setProperty('--text-primary', designTokens.colors.secondary[900]);
      root.style.setProperty('--text-secondary', designTokens.colors.secondary[600]);
      root.style.setProperty('--text-tertiary', designTokens.colors.secondary[500]);
      root.style.setProperty('--border-color', designTokens.colors.secondary[200]);
      root.style.setProperty('--hover-bg', designTokens.colors.secondary[100]);
      root.style.setProperty('--accent-color', designTokens.colors.primary[500]);
    }
    
    // Дополнительные переменные для статусов
    root.style.setProperty('--success-color', designTokens.colors.success[500]);
    root.style.setProperty('--warning-color', designTokens.colors.warning[500]);
    root.style.setProperty('--danger-color', designTokens.colors.danger[500]);
    root.style.setProperty('--info-color', designTokens.colors.info[500]);
    
    // Переменные для теней
    root.style.setProperty('--shadow-sm', designTokens.boxShadow.sm);
    root.style.setProperty('--shadow-md', designTokens.boxShadow.md);
    root.style.setProperty('--shadow-lg', designTokens.boxShadow.lg);
    root.style.setProperty('--shadow-xl', designTokens.boxShadow.xl);
    
  }, [theme, isDark]);

  // Слушаем изменения системной темы
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = (e) => {
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
    themeConfig,
    // Добавляем утилитарные функции
    designTokens,
    getColor,
    getSpacing,
    getFontSize,
    getShadow
  };

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  );
};

