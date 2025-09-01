import { useState, useEffect } from 'react';
import { getTheme } from '../index';

// Хук для управления темой
export const useTheme = (initialTheme = 'light') => {
  const [theme, setTheme] = useState(initialTheme);
  const [isDark, setIsDark] = useState(initialTheme === 'dark');

  useEffect(() => {
    // Проверяем сохраненную тему в localStorage
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
      setTheme(savedTheme);
      setIsDark(savedTheme === 'dark');
    } else {
      // Проверяем системную тему
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      if (prefersDark) {
        setTheme('dark');
        setIsDark(true);
      }
    }
  }, []);

  const toggleTheme = () => {
    const newTheme = theme === 'light' ? 'dark' : 'light';
    setTheme(newTheme);
    setIsDark(newTheme === 'dark');
    localStorage.setItem('theme', newTheme);
  };

  const setLightTheme = () => {
    setTheme('light');
    setIsDark(false);
    localStorage.setItem('theme', 'light');
  };

  const setDarkTheme = () => {
    setTheme('dark');
    setIsDark(true);
    localStorage.setItem('theme', 'dark');
  };

  const themeConfig = getTheme(theme);

  return {
    theme,
    isDark,
    isLight: !isDark,
    themeConfig,
    toggleTheme,
    setLightTheme,
    setDarkTheme,
    setTheme
  };
};
