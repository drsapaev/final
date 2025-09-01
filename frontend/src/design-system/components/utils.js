// Утилиты для компонентов дизайн-системы
// Импортируем designTokens напрямую, чтобы избежать циркулярных зависимостей
const designTokens = {
  colors: {
    primary: {
      50: '#eff6ff', 100: '#dbeafe', 200: '#bfdbfe', 300: '#93c5fd', 400: '#60a5fa',
      500: '#3b82f6', 600: '#2563eb', 700: '#1d4ed8', 800: '#1e40af', 900: '#1e3a8a'
    },
    secondary: {
      50: '#f8fafc', 100: '#f1f5f9', 200: '#e2e8f0', 300: '#cbd5e1', 400: '#94a3b8',
      500: '#64748b', 600: '#475569', 700: '#334155', 800: '#1e293b', 900: '#0f172a'
    },
    success: {
      50: '#f0fdf4', 100: '#dcfce7', 200: '#bbf7d0', 300: '#86efac', 400: '#4ade80',
      500: '#22c55e', 600: '#16a34a', 700: '#15803d', 800: '#166534', 900: '#14532d'
    },
    danger: {
      50: '#fef2f2', 100: '#fee2e2', 200: '#fecaca', 300: '#fca5a5', 400: '#f87171',
      500: '#ef4444', 600: '#dc2626', 700: '#b91c1c', 800: '#991b1b', 900: '#7f1d1d'
    },
    warning: {
      50: '#fffbeb', 100: '#fef3c7', 200: '#fde68a', 300: '#fcd34d', 400: '#fbbf24',
      500: '#f59e0b', 600: '#d97706', 700: '#b45309', 800: '#92400e', 900: '#78350f'
    },
    info: {
      50: '#f0f9ff', 100: '#e0f2fe', 200: '#bae6fd', 300: '#7dd3fc', 400: '#38bdf8',
      500: '#0ea5e9', 600: '#0284c7', 700: '#0369a1', 800: '#075985', 900: '#0c4a6e'
    }
  },
  typography: {
    fontSize: { xs: '12px', sm: '14px', base: '16px', lg: '18px', xl: '20px', '2xl': '24px', '3xl': '30px', '4xl': '36px', '5xl': '48px' },
    fontWeight: { normal: '400', medium: '500', semibold: '600', bold: '700' }
  },
  spacing: { xs: '4px', sm: '8px', md: '16px', lg: '24px', xl: '32px', '2xl': '48px', '3xl': '64px' },
  borderRadius: { sm: '4px', md: '8px', lg: '12px', xl: '16px', '2xl': '20px', full: '9999px' },
  boxShadow: {
    sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
    md: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
    lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
    xl: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
    '2xl': '0 25px 50px -12px rgba(0, 0, 0, 0.25)'
  },
  breakpoints: { sm: '640px', md: '768px', lg: '1024px', xl: '1280px', '2xl': '1536px' }
};

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
  return designTokens.boxShadow[size] || 'none';
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
