import React from 'react';
import { useTheme } from '../../../contexts/ThemeContext';

/**
 * macOS-style Button Component
 * Implements Apple's Human Interface Guidelines for buttons
 */
const Button = React.forwardRef(({
  children,
  variant = 'default',
  size = 'default',
  disabled = false,
  loading = false,
  fullWidth = false,
  className = '',
  style = {},
  onClick,
  ...props
}, ref) => {
  const { theme } = useTheme();

  // macOS button styles based on variant
  const getButtonStyles = () => {
    const baseStyles = {
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
      fontWeight: '500',
      borderRadius: '6px',
      border: 'none',
      cursor: disabled || loading ? 'not-allowed' : 'pointer',
      transition: 'all 0.2s cubic-bezier(0.2, 0.8, 0.2, 1)',
      position: 'relative',
      overflow: 'hidden',
      outline: 'none',
      userSelect: 'none',
      WebkitUserSelect: 'none',
      WebkitAppearance: 'none',
      MozAppearance: 'none',
      appearance: 'none'
    };

    const sizeStyles = {
      small: {
        padding: '6px 12px',
        fontSize: '11px',
        minHeight: '24px',
        gap: '4px'
      },
      default: {
        padding: '8px 16px',
        fontSize: '13px',
        minHeight: '32px',
        gap: '6px'
      },
      large: {
        padding: '12px 24px',
        fontSize: '15px',
        minHeight: '40px',
        gap: '8px'
      }
    };

    const variantStyles = {
      default: {
        backgroundColor: 'rgba(0, 0, 0, 0.05)',
        color: 'var(--mac-text-primary)',
        border: '1px solid rgba(0, 0, 0, 0.1)'
      },
      primary: {
        backgroundColor: '#007aff',
        color: 'white',
        border: '1px solid #007aff',
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.12), 0 1px 2px rgba(0, 0, 0, 0.24)'
      },
      secondary: {
        backgroundColor: 'rgba(0, 0, 0, 0.05)',
        color: 'var(--mac-text-primary)',
        border: '1px solid rgba(0, 0, 0, 0.1)'
      },
      success: {
        backgroundColor: '#34c759',
        color: 'white',
        border: '1px solid #34c759',
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.12), 0 1px 2px rgba(0, 0, 0, 0.24)'
      },
      warning: {
        backgroundColor: '#ff9500',
        color: 'white',
        border: '1px solid #ff9500',
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.12), 0 1px 2px rgba(0, 0, 0, 0.24)'
      },
      danger: {
        backgroundColor: '#ff3b30',
        color: 'white',
        border: '1px solid #ff3b30',
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.12), 0 1px 2px rgba(0, 0, 0, 0.24)'
      },
      ghost: {
        backgroundColor: 'transparent',
        color: 'var(--mac-text-primary)',
        border: '1px solid transparent'
      },
      link: {
        backgroundColor: 'transparent',
        color: '#007aff',
        border: 'none',
        padding: '4px 8px',
        textDecoration: 'none'
      }
    };

    return {
      ...baseStyles,
      ...sizeStyles[size],
      ...variantStyles[variant],
      ...(fullWidth && { width: '100%' }),
      ...(disabled && {
        opacity: 0.5,
        pointerEvents: 'none'
      }),
      ...style
    };
  };

  const handleClick = (e) => {
    if (disabled || loading) return;

    // Add subtle haptic feedback simulation
    if (navigator.vibrate) {
      navigator.vibrate(10);
    }

    if (onClick) {
      onClick(e);
    }
  };

  const buttonStyles = getButtonStyles();

  return (
    <button
      ref={ref}
      className={`mac-button ${className}`}
      style={buttonStyles}
      disabled={disabled || loading}
      onClick={handleClick}
      {...props}
    >
      {/* Loading spinner */}
      {loading && (
        <svg
          className="mac-button-spinner"
          style={{
            width: '14px',
            height: '14px',
            marginRight: '6px',
            animation: 'mac-spin 1s linear infinite'
          }}
          viewBox="0 0 24 24"
          fill="none"
        >
          <circle
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="2"
            strokeDasharray="8 8"
            strokeLinecap="round"
          />
        </svg>
      )}

      {/* Button content */}
      <span style={{ position: 'relative', zIndex: 1 }}>
        {children}
      </span>

      {/* Hover effect overlay */}
      {!disabled && !loading && (
        <div
          className="mac-button-overlay"
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(255, 255, 255, 0.1)',
            opacity: 0,
            transition: 'opacity 0.2s cubic-bezier(0.2, 0.8, 0.2, 1)',
            pointerEvents: 'none',
            borderRadius: 'inherit'
          }}
        />
      )}

      <style jsx>{`
        @keyframes mac-spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }

        button:hover .mac-button-overlay {
          opacity: 1 !important;
        }

        button:active {
          transform: scale(0.98) !important;
        }

        /* Focus ring for accessibility */
        button:focus-visible {
          outline: 2px solid #007aff;
          outline-offset: 2px;
        }

        /* Dark mode adjustments */
        @media (prefers-color-scheme: dark) {
          button {
            color-scheme: dark;
          }
        }

        /* Reduced motion */
        @media (prefers-reduced-motion: reduce) {
          button {
            transition: none;
          }

          .mac-button-spinner {
            animation: none;
          }

          button:active {
            transform: none !important;
          }
        }
      `}</style>
    </button>
  );
});

Button.displayName = 'macOS Button';

export default Button;
