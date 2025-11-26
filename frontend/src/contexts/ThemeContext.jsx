import React, { createContext, useContext, useState, useEffect } from 'react';
import tokens, { colors as tokenColors } from '../theme/tokens';

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
  const themeConfig = { mode: theme };

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
    return tokens?.spacing?.[size] || tokens?.spacing?.md || '16px';
  };

  const getFontSize = (size) => {
    return tokens?.typography?.fontSize?.[size] || tokens?.typography?.fontSize?.base || '16px';
  };

  const getShadow = (size) => {
    return tokens?.shadows?.[size] || tokens?.shadows?.md || '0 4px 6px -1px rgba(0, 0, 0, 0.1)';
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
    
    // Check if custom color scheme is active
    const isCustomScheme = localStorage.getItem('customColorScheme') === 'true';
    const activeSchemeId = localStorage.getItem('activeColorSchemeId');
    
    // Применяем CSS классы к body и document
    document.body.classList.remove('light-theme', 'dark-theme');
    
    if (isCustomScheme && activeSchemeId) {
      // Apply custom scheme variables (синхронизировано с ColorSchemeSelector)
      const root = document.documentElement;
      // Полная нормализация: убираем светлую/тёмную тему и их атрибуты
      document.body.classList.remove('light-theme', 'dark-theme');
      document.documentElement.removeAttribute('data-theme');
      document.documentElement.setAttribute('data-color-scheme', activeSchemeId);
      // Базовые нейтральные переменные, чтобы исключить влияние предыдущей темы
      root.style.setProperty('--accent', 'var(--mac-accent-blue)');
      root.style.setProperty('--mac-border', 'rgba(255,255,255,0.22)');
      root.style.setProperty('--mac-border-secondary', 'rgba(255,255,255,0.18)');
      root.style.setProperty('--mac-separator', 'rgba(255,255,255,0.18)');
      
      if (activeSchemeId === 'vibrant') {
        // Матовые приглушённые цвета
        root.style.setProperty('--mac-bg-primary', '#6b8db3'); /* Приглушённый синий */
        root.style.setProperty('--mac-bg-secondary', '#7fa899'); /* Приглушённый бирюзовый */
        root.style.setProperty('--mac-accent-blue', '#d4a063'); /* Приглушённый оранжевый */
        root.style.setProperty('--mac-text-primary', '#ffffff');
        root.style.setProperty('--mac-text-secondary', 'rgba(255,255,255,0.92)');
        root.style.setProperty('--mac-gradient-window', 'linear-gradient(135deg, rgba(107, 141, 179, 0.75) 0%, rgba(127, 168, 153, 0.7) 40%, rgba(212, 160, 99, 0.65) 80%), linear-gradient(135deg, rgba(120, 130, 145, 0.3) 0%, rgba(130, 140, 150, 0.25) 100%)');
        root.style.setProperty('--mac-gradient-sidebar', 'linear-gradient(135deg, rgba(100, 130, 165, 0.7) 0%, rgba(115, 155, 140, 0.65) 45%, rgba(200, 150, 90, 0.6) 100%), linear-gradient(135deg, rgba(130, 140, 150, 0.25) 0%, rgba(140, 150, 160, 0.2) 100%)');
        root.style.setProperty('--bg', '#6b8db3');
        root.style.setProperty('--mac-bg-toolbar', 'rgba(30, 35, 45, 0.4)');
        root.style.setProperty('--mac-separator', 'rgba(255,255,255,0.22)');
        root.style.setProperty('--mac-border', 'rgba(255,255,255,0.22)');
        root.style.setProperty('--mac-border-secondary', 'rgba(255,255,255,0.18)');
      } else if (activeSchemeId === 'glass') {
        // Синхронизировано с macos.css [data-color-scheme="glass"]
        // Улучшенные значения для лучшей видимости карточек
        root.style.setProperty('--mac-bg-primary', 'rgba(50, 55, 65, 0.75)');
        root.style.setProperty('--mac-bg-secondary', 'rgba(60, 65, 75, 0.65)');
        root.style.setProperty('--mac-bg-toolbar', 'rgba(50, 55, 65, 0.85)'); /* Увеличенная непрозрачность для хедера */
        root.style.setProperty('--mac-bg-tertiary', 'rgba(70, 75, 85, 0.55)');
        root.style.setProperty('--mac-accent-blue', 'rgba(0,122,255,0.8)');
        root.style.setProperty('--mac-text-primary', '#f0f1f5');
        root.style.setProperty('--mac-text-secondary', 'rgba(240,240,245,0.9)');
        root.style.setProperty('--mac-border', 'rgba(255, 255, 255, 0.2)');
        root.style.setProperty('--mac-border-secondary', 'rgba(255, 255, 255, 0.15)');
        root.style.setProperty('--mac-blur-light', 'saturate(180%) blur(22px)');
        root.style.setProperty('--surface', 'rgba(255,255,255,0.25)');
        root.style.setProperty('--bg', '#f6f7f9');
        root.style.setProperty('--mac-success', '#34c759');
        root.style.setProperty('--mac-warning', '#ff9500');
        root.style.setProperty('--mac-error', '#ff3b30');
        // Очищаем градиент из предыдущих тем
        root.style.setProperty('--mac-gradient-window', 'none');
        // Дополнительно фиксируем фон и backdrop-filter на html и body
        document.documentElement.style.background = 'rgba(20, 20, 25, 0.3)';
        document.documentElement.style.backdropFilter = 'blur(22px) saturate(160%)';
        document.documentElement.style.webkitBackdropFilter = 'blur(22px) saturate(160%)';
        document.body.style.background = 'rgba(20, 20, 25, 0.3)';
        document.body.style.backdropFilter = 'blur(22px) saturate(160%)';
        document.body.style.webkitBackdropFilter = 'blur(22px) saturate(160%)';
      } else if (activeSchemeId === 'gradient') {
        // Синхронизация с предпросмотром в Settings → Gradient
        root.style.setProperty('--mac-bg-primary', '#667eea');
        root.style.setProperty('--mac-bg-secondary', '#764ba2');
        root.style.setProperty('--mac-bg-tertiary', '#8e7cc3');
        root.style.setProperty('--mac-accent-blue', '#f093fb');
        root.style.setProperty('--mac-text-primary', '#ffffff');
        root.style.setProperty('--mac-text-secondary', 'rgba(255,255,255,0.9)');
        root.style.setProperty('--mac-border', 'rgba(255, 255, 255, 0.18)');
        root.style.setProperty('--mac-border-secondary', 'rgba(255, 255, 255, 0.14)');
        root.style.setProperty('--mac-separator', 'rgba(255, 255, 255, 0.16)');
        root.style.setProperty('--mac-gradient-window', 'linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%)');
        root.style.setProperty('--bg', 'transparent');
        // Для бесшовности — прозрачные фоновые слои у элементов
        root.style.setProperty('--mac-bg-toolbar', 'transparent');
        root.style.setProperty('--mac-gradient-sidebar', 'transparent');
        root.style.setProperty('--mac-success', '#34c759');
        root.style.setProperty('--mac-warning', '#ff9500');
        root.style.setProperty('--mac-error', '#ff3b30');
        // Сбрасываем эффект стекла, если он был установлен ранее
        document.documentElement.style.background = '';
        document.documentElement.style.backdropFilter = '';
        document.documentElement.style.webkitBackdropFilter = '';
        document.body.style.background = '';
        document.body.style.backdropFilter = '';
        document.body.style.webkitBackdropFilter = '';
      }
      
      // Don't apply standard theme variables
      return;
    } else {
      document.body.classList.add(`${theme}-theme`);
      document.documentElement.setAttribute('data-theme', theme);
      // Clear any custom scheme attribute
      document.documentElement.removeAttribute('data-color-scheme');
    }
    
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
    root.style.setProperty('--shadow-sm', tokens?.shadows?.sm || '0 1px 2px 0 rgba(0, 0, 0, 0.05)');
    root.style.setProperty('--shadow-md', tokens?.shadows?.md || '0 4px 6px -1px rgba(0, 0, 0, 0.1)');
    root.style.setProperty('--shadow-lg', tokens?.shadows?.lg || '0 10px 15px -3px rgba(0, 0, 0, 0.1)');
    root.style.setProperty('--shadow-xl', tokens?.shadows?.xl || '0 20px 25px -5px rgba(0, 0, 0, 0.1)');
    
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
    designTokens: tokens,
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

