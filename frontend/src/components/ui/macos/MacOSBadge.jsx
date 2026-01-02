import React from 'react';

const MacOSBadge = ({
  children,
  variant = 'default',
  size = 'md',
  className = '',
  style = {},
  outline, // Destructure to prevent passing boolean to DOM
  ...props
}) => {
  // Размеры бейджей
  const sizeStyles = {
    sm: {
      padding: '2px 6px',
      fontSize: 'var(--mac-font-size-xs)',
      borderRadius: 'var(--mac-radius-sm)',
      minHeight: '16px'
    },
    md: {
      padding: '4px 8px',
      fontSize: 'var(--mac-font-size-sm)',
      borderRadius: 'var(--mac-radius-sm)',
      minHeight: '20px'
    },
    lg: {
      padding: '6px 12px',
      fontSize: 'var(--mac-font-size-base)',
      borderRadius: 'var(--mac-radius-md)',
      minHeight: '24px'
    }
  };

  // Варианты бейджей
  const variantStyles = {
    default: {
      backgroundColor: 'var(--mac-bg-secondary)',
      color: 'var(--mac-text-primary)',
      border: '1px solid var(--mac-border)'
    },
    primary: {
      backgroundColor: 'var(--mac-accent-blue)',
      color: 'var(--mac-text-on-accent)',
      border: '1px solid var(--mac-accent-blue)'
    },
    secondary: {
      backgroundColor: 'var(--mac-bg-tertiary)',
      color: 'var(--mac-text-secondary)',
      border: '1px solid var(--mac-border)'
    },
    success: {
      backgroundColor: 'var(--mac-success)',
      color: 'var(--mac-text-on-success)',
      border: '1px solid var(--mac-success)'
    },
    warning: {
      backgroundColor: 'var(--mac-warning)',
      color: 'var(--mac-text-on-warning)',
      border: '1px solid var(--mac-warning)'
    },
    error: {
      backgroundColor: 'var(--mac-error)',
      color: 'var(--mac-text-on-error)',
      border: '1px solid var(--mac-error)'
    },
    info: {
      backgroundColor: 'var(--mac-info)',
      color: 'var(--mac-text-on-info)',
      border: '1px solid var(--mac-info)'
    },
    outline: {
      backgroundColor: 'transparent',
      color: 'var(--mac-text-primary)',
      border: '1px solid var(--mac-border)'
    },
    ghost: {
      backgroundColor: 'transparent',
      color: 'var(--mac-text-secondary)',
      border: 'none'
    }
  };

  const baseStyles = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontWeight: 'var(--mac-font-weight-medium)',
    borderRadius: 'var(--mac-radius-sm)',
    textAlign: 'center',
    whiteSpace: 'nowrap',
    userSelect: 'none',
    ...sizeStyles[size],
    ...variantStyles[variant]
  };

  return (
    <span
      className={className}
      style={{
        ...baseStyles,
        ...style
      }}
      {...props}
    >
      {children}
    </span>
  );
};

export default MacOSBadge;
