import React from 'react';
import { Loader2 } from 'lucide-react';

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
  // Варианты кнопок
  const variants = {
    primary: {
      background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
      color: 'white',
      boxShadow: '0 4px 14px 0 rgba(59, 130, 246, 0.3)'
    },
    secondary: {
      background: 'linear-gradient(135deg, #6b7280 0%, #4b5563 100%)',
      color: 'white',
      boxShadow: '0 4px 14px 0 rgba(107, 114, 128, 0.3)'
    },
    success: {
      background: 'linear-gradient(135deg, #22c55e 0%, #16a34a 100%)',
      color: 'white',
      boxShadow: '0 4px 14px 0 rgba(34, 197, 94, 0.3)'
    },
    danger: {
      background: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
      color: 'white',
      boxShadow: '0 4px 14px 0 rgba(239, 68, 68, 0.3)'
    },
    warning: {
      background: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
      color: '#212529',
      boxShadow: '0 4px 14px 0 rgba(245, 158, 11, 0.3)'
    },
    ghost: {
      background: 'transparent',
      color: 'inherit',
      boxShadow: 'none',
      border: '1px solid rgba(255, 255, 255, 0.2)'
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
