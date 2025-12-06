/**
 * Улучшенный провайдер темы с поддержкой токенов дизайна
 */

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { getTheme, applyCSSVariables, lightTheme, darkTheme } from './themes';
import { tokens } from './tokens';
import logger from '../utils/logger';
import '../theme/macos-tokens.css';

// Утилиты для работы с токенами дизайна
const getColor = (colorName, shade = 500) => {
  return `var(--mac-${colorName}${shade !== 500 ? `-${shade}` : ''})`;
};

const getSpacing = (size) => {
  const spacingMap = {
    xs: '4px',
    sm: '8px',
    md: '16px',
    lg: '24px',
    xl: '32px',
    '2xl': '48px',
    '3xl': '64px'
  };
  return spacingMap[size] || size;
};

const getFontSize = (size) => {
  const fontSizeMap = {
    xs: '11px',
    sm: '12px',
    base: '13px',
    lg: '15px',
    xl: '17px',
    '2xl': '22px',
    '3xl': '28px'
  };
  return fontSizeMap[size] || size;
};

const getShadow = (size) => {
  const shadowMap = {
    sm: '0 1px 3px rgba(0, 0, 0, 0.12), 0 1px 2px rgba(0, 0, 0, 0.24)',
    md: '0 4px 12px rgba(0, 0, 0, 0.15)',
    lg: '0 10px 25px rgba(0, 0, 0, 0.15)',
    xl: '0 20px 40px rgba(0, 0, 0, 0.15)'
  };
  return shadowMap[size] || size;
};

// Контекст темы
const ThemeContext = createContext({
  theme: lightTheme,
  themeName: 'light',
  tokens,
  setTheme: () => {},
  toggleTheme: () => {},
  isDark: false,
  isLight: true,
  getColor,
  getSpacing,
  getFontSize,
  getShadow
});

// Хук для использования темы
export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};

// Провайдер темы
export const ThemeProvider = ({ children, defaultTheme = 'light' }) => {
  const [themeName, setThemeName] = useState(() => {
    // Проверяем localStorage
    const saved = localStorage.getItem('theme');
    if (saved && ['light', 'dark'].includes(saved)) {
      return saved;
    }
    
    // Проверяем системные предпочтения
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark';
    }
    
    return defaultTheme;
  });

  const [theme, setThemeState] = useState(() => getTheme(themeName));

  // Функция для смены темы
  const setTheme = useCallback((newThemeName) => {
    if (!['light', 'dark'].includes(newThemeName)) {
      logger.warn(`Invalid theme name: ${newThemeName}. Using 'light' instead.`);
      newThemeName = 'light';
    }
    
    setThemeName(newThemeName);
    setThemeState(getTheme(newThemeName));
    localStorage.setItem('theme', newThemeName);
  }, []);

  // Функция для переключения темы
  const toggleTheme = useCallback(() => {
    setTheme(themeName === 'light' ? 'dark' : 'light');
  }, [themeName, setTheme]);

  // Применяем CSS переменные при изменении темы
  useEffect(() => {
    applyCSSVariables(theme);
    
    // Добавляем класс темы к body
    document.body.className = document.body.className
      .replace(/theme-\w+/g, '')
      .trim();
    document.body.classList.add(`theme-${themeName}`);
    
    // Устанавливаем атрибут data-theme для CSS селекторов
    document.documentElement.setAttribute('data-theme', themeName);
    
    // Мета-тег для цвета статус-бара на мобильных устройствах
    const metaThemeColor = document.querySelector('meta[name="theme-color"]');
    if (metaThemeColor) {
      metaThemeColor.setAttribute('content', theme.colors.background.primary);
    } else {
      const meta = document.createElement('meta');
      meta.name = 'theme-color';
      meta.content = theme.colors.background.primary;
      document.head.appendChild(meta);
    }
  }, [theme, themeName]);

  // Слушаем изменения системных предпочтений
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    
    const handleChange = (e) => {
      // Только если пользователь не установил тему вручную
      const savedTheme = localStorage.getItem('theme');
      if (!savedTheme) {
        setTheme(e.matches ? 'dark' : 'light');
      }
    };

    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, [setTheme]);

  // Значения контекста
  const contextValue = {
    theme,
    themeName,
    tokens,
    setTheme,
    toggleTheme,
    isDark: themeName === 'dark',
    isLight: themeName === 'light',

    // macOS утилиты для работы с токенами дизайна
    getColor,
    getSpacing,
    getFontSize,
    getShadow
  };

  return (
    <ThemeContext.Provider value={contextValue}>
      {children}
    </ThemeContext.Provider>
  );
};

// HOC для компонентов, которым нужна тема
export const withTheme = (Component) => {
  return function ThemedComponent(props) {
    const theme = useTheme();
    return <Component {...props} theme={theme} />;
  };
};

// Хук для адаптивных значений
export const useResponsiveValue = (values) => {
  const [currentValue, setCurrentValue] = useState(values.base || values);
  
  useEffect(() => {
    const updateValue = () => {
      const width = window.innerWidth;
      
      if (width >= parseInt(tokens.breakpoints['2xl']) && values['2xl'] !== undefined) {
        setCurrentValue(values['2xl']);
      } else if (width >= parseInt(tokens.breakpoints.xl) && values.xl !== undefined) {
        setCurrentValue(values.xl);
      } else if (width >= parseInt(tokens.breakpoints.lg) && values.lg !== undefined) {
        setCurrentValue(values.lg);
      } else if (width >= parseInt(tokens.breakpoints.md) && values.md !== undefined) {
        setCurrentValue(values.md);
      } else if (width >= parseInt(tokens.breakpoints.sm) && values.sm !== undefined) {
        setCurrentValue(values.sm);
      } else {
        setCurrentValue(values.base || values);
      }
    };
    
    updateValue();
    window.addEventListener('resize', updateValue);
    return () => window.removeEventListener('resize', updateValue);
  }, [values]);
  
  return currentValue;
};

export default ThemeProvider;


