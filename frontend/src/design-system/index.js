/**
 * Базовая дизайн-система для совместимости
 * После отката миграции - предоставляет минимальный API
 * TODO: Постепенно заменить на нативные компоненты
 */
import React from 'react';

export const designTokens = {
  colors: {
    primary: {
      400: '#60a5fa',
      500: '#3b82f6',
      600: '#2563eb',
      700: '#1d4ed8'
    },
    secondary: {
      50: '#f8fafc',
      100: '#f1f5f9',
      200: '#e2e8f0',
      300: '#cbd5e1',
      400: '#94a3b8',
      500: '#64748b',
      600: '#475569',
      700: '#334155',
      800: '#1e293b',
      900: '#0f172a'
    },
    success: {
      500: '#10b981'
    },
    warning: {
      500: '#f59e0b'
    },
    danger: {
      500: '#ef4444'
    },
    info: {
      500: '#06b6d4'
    }
  },
  spacing: {
    xs: '4px',
    sm: '8px',
    md: '16px',
    lg: '24px',
    xl: '32px'
  },
  typography: {
    fontSize: {
      base: '16px',
      sm: '14px',
      lg: '18px',
      xl: '20px'
    }
  },
  boxShadow: {
    sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
    md: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
    lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
    xl: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
  }
};

export const themes = {
  light: {
    background: '#ffffff',
    surface: '#f8fafc',
    text: '#1e293b',
    textSecondary: '#64748b',
    border: '#e2e8f0',
    accent: designTokens.colors.primary[500]
  },
  dark: {
    background: '#0f172a',
    surface: '#1e293b',
    text: '#f8fafc',
    textSecondary: '#94a3b8',
    border: '#334155',
    accent: designTokens.colors.primary[400]
  }
};

// Базовые React компоненты для совместимости

export const Button = ({ children, className = '', ...props }) => {
  return React.createElement('button', {
    className: `px-4 py-2 rounded ${className}`,
    ...props
  }, children);
};

export const Card = ({ children, className = '', ...props }) => {
  return React.createElement('div', {
    className: `bg-white rounded-lg shadow ${className}`,
    ...props
  }, children);
};

export const Badge = ({ children, className = '', variant = 'default', ...props }) => {
  const variantClasses = {
    default: 'bg-gray-100 text-gray-800',
    primary: 'bg-blue-100 text-blue-800',
    success: 'bg-green-100 text-green-800',
    warning: 'bg-yellow-100 text-yellow-800',
    danger: 'bg-red-100 text-red-800'
  };
  
  return React.createElement('span', {
    className: `inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${variantClasses[variant]} ${className}`,
    ...props
  }, children);
};

export const Skeleton = ({ className = '', ...props }) => {
  return React.createElement('div', {
    className: `animate-pulse bg-gray-200 rounded ${className}`,
    ...props
  });
};

export const AnimatedTransition = ({ children, className = '', ...props }) => {
  return React.createElement('div', {
    className: `transition-all duration-200 ${className}`,
    ...props
  }, children);
};

// Хуки-заглушки
export const useBreakpoint = () => ({
  isMobile: false,
  isTablet: false,
  isDesktop: true
});

export const useTouchDevice = () => false;

// Утилиты для работы с дизайн-системой
export const getTheme = (theme = 'light') => themes[theme];
export const getColor = (color, shade = 500) => designTokens.colors[color]?.[shade];
export const getSpacing = (size) => designTokens.spacing[size];
export const getFontSize = (size) => designTokens.typography?.fontSize?.[size];
export const getShadow = (size) => designTokens.boxShadow?.[size];

export default designTokens;
