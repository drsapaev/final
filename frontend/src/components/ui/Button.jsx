import React from 'react';
import { Loader2 } from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';

const Button = ({
  children,
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled = false,
  success = false,
  onClick,
  style = {},
  className = '',
  ...props
}) => {
  const { isDark, isLight, getColor, getSpacing, getFontSize } = useTheme();

  // Варианты кнопок с использованием централизованной темы
  const variants = {
    primary: {
      background: `linear-gradient(135deg, ${getColor('primary', 500)} 0%, ${getColor('primary', 600)} 100%)`,
      color: 'white',
      boxShadow: `0 4px 14px 0 ${getColor('primary', 500)}30`
    },
    secondary: {
      background: `linear-gradient(135deg, ${getColor('secondary', 500)} 0%, ${getColor('secondary', 600)} 100%)`,
      color: 'white',
      boxShadow: `0 4px 14px 0 ${getColor('secondary', 500)}30`
    },
    success: {
      background: `linear-gradient(135deg, ${getColor('success', 500)} 0%, ${getColor('success', 600)} 100%)`,
      color: 'white',
      boxShadow: `0 4px 14px 0 ${getColor('success', 500)}30`
    },
    danger: {
      background: `linear-gradient(135deg, ${getColor('danger', 500)} 0%, ${getColor('danger', 600)} 100%)`,
      color: 'white',
      boxShadow: `0 4px 14px 0 ${getColor('danger', 500)}30`
    },
    warning: {
      background: `linear-gradient(135deg, ${getColor('warning', 500)} 0%, ${getColor('warning', 600)} 100%)`,
      color: 'white',
      boxShadow: `0 4px 14px 0 ${getColor('warning', 500)}30`
    },
    ghost: {
      background: 'transparent',
      color: isLight ? getColor('primary', 500) : getColor('primary', 400),
      boxShadow: 'none',
      border: `1px solid ${isLight ? getColor('primary', 500) : getColor('primary', 400)}`
    }
  };

  // Размеры кнопок
  const sizes = {
    xs: {
      padding: '4px 8px',
      fontSize: '12px',
      borderRadius: '6px'
    },
    sm: {
      padding: '8px 16px',
      fontSize: '14px',
      borderRadius: '8px'
    },
    md: {
      padding: '12px 24px',
      fontSize: '14px',
      borderRadius: '12px'
    },
    lg: {
      padding: '16px 32px',
      fontSize: '16px',
      borderRadius: '12px'
    },
    xl: {
      padding: '20px 40px',
      fontSize: '18px',
      borderRadius: '16px'
    }
  };

  // Базовые стили
  const baseStyles = {
    border: 'none',
    cursor: disabled || loading ? 'not-allowed' : 'pointer',
    fontWeight: '600',
    lineHeight: '1.25',
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    position: 'relative',
    overflow: 'hidden',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
    opacity: disabled ? 0.6 : 1,
    transform: 'translateY(0)',
    ...variants[variant],
    ...sizes[size]
  };

  // Hover эффекты
  const hoverStyles = {
    transform: 'translateY(-2px)',
    boxShadow: variants[variant].boxShadow.replace('0.3', '0.4')
  };

  // Success состояние
  const successStyles = success ? {
    background: 'linear-gradient(135deg, #22c55e 0%, #16a34a 100%)',
    color: 'white'
  } : {};

  const handleMouseEnter = (e) => {
    if (!disabled && !loading) {
      Object.assign(e.target.style, hoverStyles);
    }
  };

  const handleMouseLeave = (e) => {
    if (!disabled && !loading) {
      e.target.style.transform = 'translateY(0)';
      e.target.style.boxShadow = variants[variant].boxShadow;
    }
  };

  return (
    <button
      style={{
        ...baseStyles,
        ...successStyles,
        ...style
      }}
      className={className}
      onClick={onClick}
      disabled={disabled || loading}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      {...props}
    >
      {loading && <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />}
      {children}
    </button>
  );
};

export default Button;
