import React, { createContext, useContext, useState, useEffect } from 'react';
import { designTokens, themes } from '../design-system';
import { colors as tokenColors } from '../theme/tokens';

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

  // Утилитарные функции для работы с токенами (обновлены на новую систему)
  const getColor = (color, shade = 500) => {
    // Используем консолидированную цветовую систему
    if (color === 'primary' || color === 'secondary') {
      return tokenColors[color]?.[shade] || tokenColors.primary?.[500] || '#0ea5e9';
    } else if (color === 'success' || color === 'warning' || color === 'danger' || color === 'info') {
      return tokenColors.status?.[color] || tokenColors.primary?.[500] || '#0ea5e9';
    } else if (color === 'text' || color === 'background' || color === 'border' || color === 'surface') {
      return tokenColors.semantic?.[color]?.primary || '#ffffff';
    }
    return tokenColors.primary?.[500] || '#0ea5e9';
  };

  const getSpacing = (size) => {
    return designTokens?.spacing?.[size] || designTokens?.spacing?.md || '16px';
  };

  const getFontSize = (size) => {
    return designTokens?.typography?.fontSize?.[size] || designTokens?.typography?.fontSize?.base || '16px';
  };

  const getShadow = (size) => {
    return designTokens?.boxShadow?.[size] || designTokens?.boxShadow?.md || '0 4px 6px -1px rgba(0, 0, 0, 0.1)';
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
      // Темная тема (обновлена на новую цветовую систему)
      root.style.setProperty('--bg-primary', tokenColors.semantic.background.primary);
      root.style.setProperty('--bg-secondary', tokenColors.semantic.background.secondary);
      root.style.setProperty('--bg-tertiary', tokenColors.gray[700]);
      root.style.setProperty('--text-primary', tokenColors.semantic.text.primary);
      root.style.setProperty('--text-secondary', tokenColors.semantic.text.secondary);
      root.style.setProperty('--text-tertiary', tokenColors.gray[400]);
      root.style.setProperty('--border-color', tokenColors.semantic.border.medium);
      root.style.setProperty('--hover-bg', tokenColors.semantic.surface.hover);
      root.style.setProperty('--accent-color', tokenColors.primary[400]);
    } else {
      // Светлая тема (обновлена на новую цветовую систему)
      root.style.setProperty('--bg-primary', tokenColors.semantic.background.primary);
      root.style.setProperty('--bg-secondary', tokenColors.semantic.background.secondary);
      root.style.setProperty('--bg-tertiary', tokenColors.gray[100]);
      root.style.setProperty('--text-primary', tokenColors.semantic.text.primary);
      root.style.setProperty('--text-secondary', tokenColors.semantic.text.secondary);
      root.style.setProperty('--text-tertiary', tokenColors.gray[500]);
      root.style.setProperty('--border-color', tokenColors.semantic.border.medium);
      root.style.setProperty('--hover-bg', tokenColors.semantic.surface.hover);
      root.style.setProperty('--accent-color', tokenColors.primary[500]);
    }
    
    // Дополнительные переменные для статусов (обновлены на новую систему)
    root.style.setProperty('--success-color', tokenColors.status.success);
    root.style.setProperty('--warning-color', tokenColors.status.warning);
    root.style.setProperty('--danger-color', tokenColors.status.danger);
    root.style.setProperty('--info-color', tokenColors.status.info);
    
    // Переменные для теней
    root.style.setProperty('--shadow-sm', designTokens?.boxShadow?.sm || '0 1px 2px 0 rgba(0, 0, 0, 0.05)');
    root.style.setProperty('--shadow-md', designTokens?.boxShadow?.md || '0 4px 6px -1px rgba(0, 0, 0, 0.1)');
    root.style.setProperty('--shadow-lg', designTokens?.boxShadow?.lg || '0 10px 15px -3px rgba(0, 0, 0, 0.1)');
    root.style.setProperty('--shadow-xl', designTokens?.boxShadow?.xl || '0 20px 25px -5px rgba(0, 0, 0, 0.1)');
    
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

