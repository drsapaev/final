// Утилиты для компонентов дизайн-системы
import { designTokens } from '../index';

// Функции для работы с токенами
const getColor = (color, shade) => {
  return designTokens.colors[color]?.[shade] || '#000000';
};

const getSpacing = (size) => {
  return designTokens.spacing[size] || '0px';
};

const getFontSize = (size) => {
  return designTokens.typography.fontSize[size] || '16px';
};

const getShadow = (size) => {
  return designTokens.shadows[size] || 'none';
};

// Функция для создания стилей кнопки
export const createButtonStyles = (variant, size, disabled = false) => {
  const baseStyles = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: getSpacing('sm'),
    border: 'none',
    borderRadius: designTokens.borderRadius.lg,
    fontWeight: designTokens.typography.fontWeight.semibold,
    cursor: disabled ? 'not-allowed' : 'pointer',
    transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
    textDecoration: 'none',
    outline: 'none',
    position: 'relative',
    overflow: 'hidden'
  };

  // Размеры
  const sizes = {
    sm: {
      padding: '8px 16px',
      fontSize: getFontSize('sm'),
      height: '32px',
      minWidth: '80px'
    },
    md: {
      padding: '12px 24px',
      fontSize: getFontSize('base'),
      height: '40px',
      minWidth: '100px'
    },
    lg: {
      padding: '16px 32px',
      fontSize: getFontSize('lg'),
      height: '48px',
      minWidth: '120px'
    }
  };

  // Варианты
  const variants = {
    primary: {
      background: `linear-gradient(135deg, ${getColor('primary', 500)} 0%, ${getColor('primary', 600)} 100%)`,
      color: 'white',
      boxShadow: `0 4px 14px 0 ${getColor('primary', 500)}30`,
      '&:hover': {
        background: `linear-gradient(135deg, ${getColor('primary', 600)} 0%, ${getColor('primary', 700)} 100%)`,
        boxShadow: `0 6px 20px 0 ${getColor('primary', 500)}40`,
        transform: 'translateY(-2px)'
      },
      '&:active': {
        transform: 'translateY(0)',
        boxShadow: `0 2px 8px 0 ${getColor('primary', 500)}30`
      }
    },
    secondary: {
      background: `linear-gradient(135deg, ${getColor('secondary', 500)} 0%, ${getColor('secondary', 600)} 100%)`,
      color: 'white',
      boxShadow: `0 4px 14px 0 ${getColor('secondary', 500)}30`,
      '&:hover': {
        background: `linear-gradient(135deg, ${getColor('secondary', 600)} 0%, ${getColor('secondary', 700)} 100%)`,
        boxShadow: `0 6px 20px 0 ${getColor('secondary', 500)}40`,
        transform: 'translateY(-2px)'
      }
    },
    success: {
      background: `linear-gradient(135deg, ${getColor('success', 500)} 0%, ${getColor('success', 600)} 100%)`,
      color: 'white',
      boxShadow: `0 4px 14px 0 ${getColor('success', 500)}30`,
      '&:hover': {
        background: `linear-gradient(135deg, ${getColor('success', 600)} 0%, ${getColor('success', 700)} 100%)`,
        boxShadow: `0 6px 20px 0 ${getColor('success', 500)}40`,
        transform: 'translateY(-2px)'
      }
    },
    danger: {
      background: `linear-gradient(135deg, ${getColor('danger', 500)} 0%, ${getColor('danger', 600)} 100%)`,
      color: 'white',
      boxShadow: `0 4px 14px 0 ${getColor('danger', 500)}30`,
      '&:hover': {
        background: `linear-gradient(135deg, ${getColor('danger', 600)} 0%, ${getColor('danger', 700)} 100%)`,
        boxShadow: `0 6px 20px 0 ${getColor('danger', 500)}40`,
        transform: 'translateY(-2px)'
      }
    },
    warning: {
      background: `linear-gradient(135deg, ${getColor('warning', 500)} 0%, ${getColor('warning', 600)} 100%)`,
      color: 'white',
      boxShadow: `0 4px 14px 0 ${getColor('warning', 500)}30`,
      '&:hover': {
        background: `linear-gradient(135deg, ${getColor('warning', 600)} 0%, ${getColor('warning', 700)} 100%)`,
        boxShadow: `0 6px 20px 0 ${getColor('warning', 500)}40`,
        transform: 'translateY(-2px)'
      }
    },
    info: {
      background: `linear-gradient(135deg, ${getColor('info', 500)} 0%, ${getColor('info', 600)} 100%)`,
      color: 'white',
      boxShadow: `0 4px 14px 0 ${getColor('info', 500)}30`,
      '&:hover': {
        background: `linear-gradient(135deg, ${getColor('info', 600)} 0%, ${getColor('info', 700)} 100%)`,
        boxShadow: `0 6px 20px 0 ${getColor('info', 500)}40`,
        transform: 'translateY(-2px)'
      }
    },
    ghost: {
      background: 'transparent',
      color: getColor('primary', 500),
      border: `1px solid ${getColor('primary', 500)}`,
      boxShadow: 'none',
      '&:hover': {
        background: getColor('primary', 50),
        transform: 'translateY(-2px)',
        boxShadow: `0 4px 14px 0 ${getColor('primary', 500)}20`
      }
    }
  };

  // Состояние disabled
  const disabledStyles = {
    opacity: 0.6,
    cursor: 'not-allowed',
    transform: 'none !important',
    boxShadow: 'none !important',
    '&:hover': {
      transform: 'none !important',
      boxShadow: 'none !important'
    }
  };

  return {
    ...baseStyles,
    ...sizes[size],
    ...variants[variant],
    ...(disabled ? disabledStyles : {})
  };
};

// Функция для создания стилей карточки
export const createCardStyles = (variant = 'default', hover = true) => {
  const baseStyles = {
    background: 'rgba(255, 255, 255, 0.8)',
    border: '1px solid rgba(255, 255, 255, 0.2)',
    borderRadius: designTokens.borderRadius['2xl'],
    boxShadow: getShadow('lg'),
    backdropFilter: 'blur(20px)',
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    overflow: 'hidden'
  };

  const variants = {
    default: {
      background: 'rgba(255, 255, 255, 0.8)',
      border: '1px solid rgba(255, 255, 255, 0.2)'
    },
    elevated: {
      background: 'rgba(255, 255, 255, 0.9)',
      border: '1px solid rgba(255, 255, 255, 0.3)',
      boxShadow: getShadow('xl')
    },
    outlined: {
      background: 'transparent',
      border: `2px solid ${getColor('primary', 200)}`,
      boxShadow: 'none'
    }
  };

  const hoverStyles = hover ? {
    '&:hover': {
      transform: 'translateY(-4px) scale(1.02)',
      boxShadow: getShadow('2xl')
    }
  } : {};

  return {
    ...baseStyles,
    ...variants[variant],
    ...hoverStyles
  };
};

// Функция для создания стилей бейджа
export const createBadgeStyles = (variant, size) => {
  const baseStyles = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: designTokens.borderRadius.full,
    fontWeight: designTokens.typography.fontWeight.medium,
    textTransform: 'uppercase',
    letterSpacing: '0.05em'
  };

  const sizes = {
    sm: {
      padding: '4px 8px',
      fontSize: getFontSize('xs'),
      height: '20px'
    },
    md: {
      padding: '6px 12px',
      fontSize: getFontSize('sm'),
      height: '24px'
    },
    lg: {
      padding: '8px 16px',
      fontSize: getFontSize('base'),
      height: '28px'
    }
  };

  const variants = {
    default: {
      background: getColor('secondary', 100),
      color: getColor('secondary', 800),
      border: `1px solid ${getColor('secondary', 200)}`
    },
    primary: {
      background: getColor('primary', 100),
      color: getColor('primary', 800),
      border: `1px solid ${getColor('primary', 200)}`
    },
    success: {
      background: getColor('success', 100),
      color: getColor('success', 800),
      border: `1px solid ${getColor('success', 200)}`
    },
    danger: {
      background: getColor('danger', 100),
      color: getColor('danger', 800),
      border: `1px solid ${getColor('danger', 200)}`
    },
    warning: {
      background: getColor('warning', 100),
      color: getColor('warning', 800),
      border: `1px solid ${getColor('warning', 200)}`
    },
    info: {
      background: getColor('info', 100),
      color: getColor('info', 800),
      border: `1px solid ${getColor('info', 200)}`
    }
  };

  return {
    ...baseStyles,
    ...sizes[size],
    ...variants[variant]
  };
};

// Функция для создания стилей скелетона
export const createSkeletonStyles = (variant, animation = 'pulse') => {
  const baseStyles = {
    backgroundColor: getColor('secondary', 200),
    borderRadius: designTokens.borderRadius.md,
    display: 'block'
  };

  const variants = {
    rectangular: {
      borderRadius: designTokens.borderRadius.md
    },
    circular: {
      borderRadius: designTokens.borderRadius.full
    },
    rounded: {
      borderRadius: designTokens.borderRadius.lg
    }
  };

  const animations = {
    pulse: {
      animation: 'skeleton-pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite'
    },
    wave: {
      animation: 'skeleton-wave 1.6s linear infinite'
    }
  };

  return {
    ...baseStyles,
    ...variants[variant],
    ...animations[animation]
  };
};

// Функция для создания медиа-запросов
export const createMediaQuery = (breakpoint) => {
  const breakpoints = designTokens.breakpoints;
  return `@media (min-width: ${breakpoints[breakpoint]})`;
};

// Функция для создания responsive стилей
export const createResponsiveStyles = (styles) => {
  return {
    ...styles.base,
    [createMediaQuery('sm')]: styles.sm || {},
    [createMediaQuery('md')]: styles.md || {},
    [createMediaQuery('lg')]: styles.lg || {},
    [createMediaQuery('xl')]: styles.xl || {}
  };
};
