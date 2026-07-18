import React, { type ReactNode, type CSSProperties, type MouseEvent } from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from '../../../i18n/useTranslation';

type ButtonVariant = 'default' | 'primary' | 'secondary' | 'success' | 'warning' | 'danger' | 'destructive' | 'error' | 'ghost' | 'outline' | 'link' | string;
type ButtonSize = 'small' | 'default' | 'large' | 'sm' | 'md' | 'lg' | string;

interface ButtonProps extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'children' | 'style' | 'onClick'> {
  children?: ReactNode;
  variant?: ButtonVariant;
  size?: ButtonSize;
  disabled?: boolean;
  loading?: boolean;
  fullWidth?: boolean;
  className?: string;
  style?: CSSProperties;
  onClick?: (e: MouseEvent<HTMLButtonElement>) => void;
  // Backward-compat props used by legacy callers
  startIcon?: ReactNode;
  endIcon?: ReactNode;
  color?: string;
  [key: string]: any;
}

type ButtonStyle = CSSProperties & {
  transition?: string;
  WebkitUserSelect?: string;
  WebkitAppearance?: string;
  MozAppearance?: string;
  WebkitBackdropFilter?: string;
};

interface SizeStyle extends CSSProperties {
  gap?: string;
}

/**
 * macOS-style Button Component
 * Implements Apple's Human Interface Guidelines for buttons
 */
const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(({
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
  const { t } = useTranslation();
  void t;

  // macOS button styles based on variant
  const getButtonStyles = (): ButtonStyle => {
    const baseStyles: ButtonStyle = {
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
      fontWeight: '400', // Стандартный вес macOS
      borderRadius: 'var(--mac-radius-md)', // Стандартный радиус macOS
      border: 'none',
      cursor: disabled || loading ? 'not-allowed' : 'pointer',
      transition: 'all var(--mac-duration-normal) var(--mac-ease)',
      position: 'relative',
      overflow: 'hidden',
      outline: 'none',
      userSelect: 'none',
      WebkitUserSelect: 'none',
      WebkitAppearance: 'none',
      MozAppearance: 'none',
      appearance: 'none'
    };

    const sizeStyles: Record<ButtonSize, SizeStyle> = {
      small: {
        padding: '6px 12px',
        fontSize: 'var(--mac-font-size-xs)',
        minHeight: '28px',
        gap: '4px'
      },
      default: {
        padding: '8px 16px',
        fontSize: 'var(--mac-font-size-base)',
        minHeight: '32px',
        gap: '6px'
      },
      large: {
        padding: '12px 20px',
        fontSize: 'var(--mac-font-size-lg)',
        minHeight: '40px',
        gap: '8px'
      }
    };

    const variantStyles: Record<ButtonVariant, CSSProperties> = {
      default: {
        backgroundColor: 'rgba(0, 0, 0, 0.05)',
        color: 'var(--mac-text-primary)',
        border: '1px solid rgba(0, 0, 0, 0.1)'
      },
      primary: {
        backgroundColor: 'var(--mac-accent-blue)',
        color: 'white',
        border: '1px solid #007aff',
        boxShadow: '0 2px 8px rgba(0, 122, 255, 0.3), 0 1px 3px rgba(0, 0, 0, 0.12)',
        backdropFilter: 'blur(10px)',
        WebkitBackdropFilter: 'blur(10px)'
      },
      secondary: {
        backgroundColor: 'rgba(255, 255, 255, 0.08)',
        color: 'var(--mac-text-primary)',
        border: '1px solid rgba(255, 255, 255, 0.15)',
        backdropFilter: 'blur(10px)',
        WebkitBackdropFilter: 'blur(10px)'
      },
      success: {
        backgroundColor: 'var(--mac-success)',
        color: 'white',
        border: '1px solid #34c759',
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.12), 0 1px 2px rgba(0, 0, 0, 0.24)'
      },
      warning: {
        backgroundColor: 'var(--mac-warning)',
        color: 'white',
        border: '1px solid #ff9500',
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.12), 0 1px 2px rgba(0, 0, 0, 0.24)'
      },
      danger: {
        backgroundColor: 'var(--mac-error)',
        color: 'white',
        border: '1px solid #ff3b30',
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.12), 0 1px 2px rgba(0, 0, 0, 0.24)'
      },
      ghost: {
        backgroundColor: 'transparent',
        color: 'var(--mac-text-primary)',
        border: '1px solid transparent',
        backdropFilter: 'blur(10px)',
        WebkitBackdropFilter: 'blur(10px)'
      },
      outline: {
        backgroundColor: 'transparent',
        color: 'var(--mac-text-primary)',
        border: '1px solid rgba(255, 255, 255, 0.3)',
        backdropFilter: 'blur(10px)',
        WebkitBackdropFilter: 'blur(10px)'
      },
      link: {
        backgroundColor: 'transparent',
        color: 'var(--mac-accent-blue)',
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
    } as ButtonStyle;
  };

  const handleClick = (e: MouseEvent<HTMLButtonElement>) => {
    if (disabled || loading) return;

    // Add subtle haptic feedback simulation
    if (typeof navigator !== 'undefined' && typeof navigator.vibrate === 'function') {
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
      aria-busy={loading}
      {...props}>

      {/* Loading spinner */}
      {loading &&
      <svg
        className="mac-button-spinner"
        style={{
          width: '14px',
          height: '14px',
          marginRight: '6px',
          animation: 'mac-spin 1s linear infinite'
        }}
        viewBox="0 0 24 24"
        fill="none">

          <circle
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="2"
          strokeDasharray="8 8"
          strokeLinecap="round" />

        </svg>
      }

      {/* Button content */}
      <span style={{ position: 'relative', zIndex: 1 }}>
        {children}
      </span>

      {/* Hover effect overlay */}
      {!disabled && !loading &&
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
        }} />

      }
    </button>);

});


Button.propTypes = {
  ...(Button.propTypes || {}),
  children: PropTypes.any,
  className: PropTypes.any,
  disabled: PropTypes.any,
  fullWidth: PropTypes.any,
  loading: PropTypes.any,
  onClick: PropTypes.any,
  size: PropTypes.any,
  style: PropTypes.any,
  variant: PropTypes.any,
};

Button.displayName = 'macOS Button';

export default Button;
