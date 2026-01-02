import React from 'react';

const MacOSButton = ({
  children,
  variant = 'default',
  size = 'md',
  disabled = false,
  loading = false,
  onClick,
  type = 'button',
  className = '',
  style = {},
  startIcon, // Destructure to prevent passing to DOM (not implemented yet)
  endIcon,   // Destructure to prevent passing to DOM (not implemented yet)
  ...props
}) => {
  // Размеры кнопок
  const sizeStyles = {
    sm: {
      padding: '6px 12px',
      fontSize: 'var(--mac-font-size-sm)',
      borderRadius: 'var(--mac-radius-sm)',
      minHeight: '28px'
    },
    md: {
      padding: '8px 16px',
      fontSize: 'var(--mac-font-size-base)',
      borderRadius: 'var(--mac-radius-md)',
      minHeight: '32px'
    },
    lg: {
      padding: '12px 24px',
      fontSize: 'var(--mac-font-size-lg)',
      borderRadius: 'var(--mac-radius-lg)',
      minHeight: '40px'
    }
  };

  // Варианты кнопок
  const variantStyles = {
    default: {
      backgroundColor: 'var(--mac-bg-secondary)',
      color: 'var(--mac-text-primary)',
      border: '1px solid var(--mac-border)',
      '&:hover': {
        backgroundColor: 'var(--mac-bg-tertiary)',
        borderColor: 'var(--mac-border-hover)'
      },
      '&:active': {
        backgroundColor: 'var(--mac-bg-quaternary)',
        transform: 'translateY(1px)'
      }
    },
    primary: {
      backgroundColor: 'var(--mac-accent-blue)',
      color: 'var(--mac-text-on-accent)',
      border: '1px solid var(--mac-accent-blue)',
      '&:hover': {
        backgroundColor: 'var(--mac-accent-blue-hover)',
        borderColor: 'var(--mac-accent-blue-hover)'
      },
      '&:active': {
        backgroundColor: 'var(--mac-accent-blue-active)',
        transform: 'translateY(1px)'
      }
    },
    secondary: {
      backgroundColor: 'var(--mac-bg-primary)',
      color: 'var(--mac-text-primary)',
      border: '1px solid var(--mac-border)',
      '&:hover': {
        backgroundColor: 'var(--mac-bg-secondary)',
        borderColor: 'var(--mac-border-hover)'
      },
      '&:active': {
        backgroundColor: 'var(--mac-bg-tertiary)',
        transform: 'translateY(1px)'
      }
    },
    outline: {
      backgroundColor: 'transparent',
      color: 'var(--mac-text-primary)',
      border: '1px solid var(--mac-border)',
      '&:hover': {
        backgroundColor: 'var(--mac-bg-secondary)',
        borderColor: 'var(--mac-border-hover)'
      },
      '&:active': {
        backgroundColor: 'var(--mac-bg-tertiary)',
        transform: 'translateY(1px)'
      }
    },
    ghost: {
      backgroundColor: 'transparent',
      color: 'var(--mac-text-primary)',
      border: 'none',
      '&:hover': {
        backgroundColor: 'var(--mac-bg-secondary)'
      },
      '&:active': {
        backgroundColor: 'var(--mac-bg-tertiary)',
        transform: 'translateY(1px)'
      }
    },
    danger: {
      backgroundColor: 'var(--mac-error)',
      color: 'var(--mac-text-on-error)',
      border: '1px solid var(--mac-error)',
      '&:hover': {
        backgroundColor: 'var(--mac-error-hover)',
        borderColor: 'var(--mac-error-hover)'
      },
      '&:active': {
        backgroundColor: 'var(--mac-error-active)',
        transform: 'translateY(1px)'
      }
    },
    success: {
      backgroundColor: 'var(--mac-success)',
      color: 'var(--mac-text-on-success)',
      border: '1px solid var(--mac-success)',
      '&:hover': {
        backgroundColor: 'var(--mac-success-hover)',
        borderColor: 'var(--mac-success-hover)'
      },
      '&:active': {
        backgroundColor: 'var(--mac-success-active)',
        transform: 'translateY(1px)'
      }
    }
  };

  const baseStyles = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontWeight: 'var(--mac-font-weight-medium)',
    cursor: disabled || loading ? 'not-allowed' : 'pointer',
    transition: 'all var(--mac-duration-normal) var(--mac-ease)',
    outline: 'none',
    textDecoration: 'none',
    userSelect: 'none',
    opacity: disabled ? 0.6 : 1,
    position: 'relative',
    overflow: 'hidden',
    ...sizeStyles[size],
    ...variantStyles[variant]
  };

  const handleClick = (e) => {
    if (disabled || loading) {
      e.preventDefault();
      e.stopPropagation();
      return;
    }
    // Для кнопок типа submit не вызываем onClick, чтобы форма могла обработать submit
    if (onClick && type !== 'submit') {
      onClick(e);
    }
  };

  const handleMouseEnter = (e) => {
    if (disabled || loading) return;
    const hoverStyles = variantStyles[variant]['&:hover'];
    if (hoverStyles) {
      Object.keys(hoverStyles).forEach(key => {
        if (key.startsWith('&:')) return;
        e.target.style[key] = hoverStyles[key];
      });
    }
  };

  const handleMouseLeave = (e) => {
    if (disabled || loading) return;
    const baseVariantStyles = variantStyles[variant];
    Object.keys(baseVariantStyles).forEach(key => {
      if (key.startsWith('&:')) return;
      e.target.style[key] = baseVariantStyles[key];
    });
  };

  const handleMouseDown = (e) => {
    if (disabled || loading) return;
    const activeStyles = variantStyles[variant]['&:active'];
    if (activeStyles) {
      Object.keys(activeStyles).forEach(key => {
        if (key.startsWith('&:')) return;
        e.target.style[key] = activeStyles[key];
      });
    }
  };

  const handleMouseUp = (e) => {
    if (disabled || loading) return;
    const baseVariantStyles = variantStyles[variant];
    Object.keys(baseVariantStyles).forEach(key => {
      if (key.startsWith('&:')) return;
      e.target.style[key] = baseVariantStyles[key];
    });
  };

  return (
    <button
      type={type}
      className={className}
      style={{
        ...baseStyles,
        ...style
      }}
      disabled={disabled || loading}
      onClick={handleClick}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onMouseDown={handleMouseDown}
      onMouseUp={handleMouseUp}
      {...props}
    >
      {loading && (
        <div
          style={{
            position: 'absolute',
            left: '50%',
            top: '50%',
            transform: 'translate(-50%, -50%)',
            width: '16px',
            height: '16px',
            border: '2px solid transparent',
            borderTop: '2px solid currentColor',
            borderRadius: '50%',
            animation: 'spin 1s linear infinite'
          }}
        />
      )}
      <span style={{ opacity: loading ? 0 : 1 }}>
        {children}
      </span>
    </button>
  );
};

export default MacOSButton;
