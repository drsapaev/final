import React from 'react';

const Badge = ({
  children,
  variant = 'default',
  size = 'md',
  className = '',
  style = {},
  ...props
}) => {
  // Варианты бейджей
  const variants = {
    default: {
      background: '#e9ecef',
      color: '#495057'
    },
    primary: {
      background: '#e3f2fd',
      color: '#1976d2'
    },
    success: {
      background: '#e8f5e8',
      color: '#388e3c'
    },
    warning: {
      background: '#fff3e0',
      color: '#f57c00'
    },
    danger: {
      background: '#ffebee',
      color: '#d32f2f'
    },
    info: {
      background: '#e3f2fd',
      color: '#1976d2'
    },
    purple: {
      background: '#f3e5f5',
      color: '#7b1fa2'
    },
    orange: {
      background: '#fff8e1',
      color: '#fbc02d'
    }
  };

  // Размеры бейджей
  const sizes = {
    xs: {
      padding: '2px 6px',
      fontSize: '10px',
      borderRadius: '4px'
    },
    sm: {
      padding: '4px 8px',
      fontSize: '12px',
      borderRadius: '6px'
    },
    md: {
      padding: '4px 8px',
      fontSize: '12px',
      borderRadius: '12px'
    },
    lg: {
      padding: '6px 12px',
      fontSize: '14px',
      borderRadius: '16px'
    }
  };

  // Базовые стили
  const baseStyles = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontWeight: '500',
    lineHeight: '1',
    transition: 'all 0.2s ease',
    ...variants[variant],
    ...sizes[size]
  };

  return (
    <span
      style={{
        ...baseStyles,
        ...style
      }}
      className={className}
      {...props}
    >
      {children}
    </span>
  );
};

export default Badge;
