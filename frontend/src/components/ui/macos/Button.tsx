import React, { type ReactNode, type CSSProperties, type MouseEvent } from 'react';
import { useTranslation } from '@/i18n/useTranslation';

// PR-UI-05: narrowed from 11 variants to 6.
// Removed: default (-> secondary), success (-> secondary + color), warning (-> secondary + color),
// destructive (-> danger), error (-> danger).
// Semantic coloring now via `color` prop on secondary variant.
type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'outline' | 'danger' | 'link' | string;
type ButtonColor = 'default' | 'success' | 'warning' | 'danger' | 'info';
type ButtonSize = 'small' | 'default' | 'large' | 'sm' | 'md' | 'lg' | string;

interface ButtonProps extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'children' | 'style' | 'onClick'> {
  children?: ReactNode;
  variant?: ButtonVariant;
  color?: ButtonColor;
  size?: ButtonSize;
  disabled?: boolean;
  loading?: boolean;
  fullWidth?: boolean;
  className?: string;
  style?: CSSProperties;
  onClick?: (e: MouseEvent<HTMLButtonElement>) => void;
  startIcon?: ReactNode;
  endIcon?: ReactNode;
  icon?: ReactNode;
  label?: ReactNode;
  action?: ReactNode;
  emptyAction?: boolean;
  as?: string;
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
  variant = 'secondary',
  color = 'default',
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

    // PR-UI-05: 6 canonical variants.
    // CC-2 (UI color-contrast track): white-ink fills use the *-strong token
    // family — the base accent #007aff / error #ff453a / success #30d158 /
    // warning #ff9f0a measure 4.02 / 3.41 / 2.02 / 2.06:1 against white, below
    // the WCAG AA 4.5:1 floor (axe color-contrast, e2e/a11y-baseline.json).
    // Strong values: #0066d6 (5.42) / #d92c20 (4.85) / #147a38 (5.43) /
    // #a86200 (4.76). Tokens come with fallbacks to the base values.
    const variantStyles: Record<string, CSSProperties> = {
      primary: {
        backgroundColor: 'var(--mac-accent-blue-strong, var(--mac-accent-blue))',
        color: 'white',
        border: '1px solid var(--mac-accent-blue-strong, #007aff)',
        boxShadow: '0 2px 8px rgba(0, 102, 214, 0.3), 0 1px 3px rgba(0, 0, 0, 0.12)'
      },
      secondary: {
        backgroundColor: 'rgba(0, 0, 0, 0.05)',
        color: 'var(--mac-text-primary)',
        border: '1px solid rgba(0, 0, 0, 0.1)'
      },
      ghost: {
        backgroundColor: 'transparent',
        color: 'var(--mac-text-primary)',
        border: '1px solid transparent'
      },
      outline: {
        backgroundColor: 'transparent',
        color: 'var(--mac-text-primary)',
        border: '1px solid rgba(255, 255, 255, 0.3)'
      },
      danger: {
        backgroundColor: 'var(--mac-danger-strong, var(--mac-error))',
        color: 'white',
        border: '1px solid var(--mac-danger-strong, #ff3b30)',
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.12), 0 1px 2px rgba(0, 0, 0, 0.24)'
      },
      link: {
        backgroundColor: 'transparent',
        // CC-2 note: link TEXT contrast is a separate latent class (dark links
        // need a brighter accent, not the dark fill token) — deliberately left
        // on the base accent; no axe-flagged link findings exist.
        color: 'var(--mac-accent-blue)',
        border: 'none',
        padding: '4px 8px',
        textDecoration: 'none'
      }
    };

    // PR-UI-05: color overrides for secondary variant (semantic coloring)
    const colorOverrides: Record<string, Partial<CSSProperties>> = {
      success: {
        backgroundColor: 'var(--mac-success-strong, var(--mac-success))',
        color: 'white',
        border: '1px solid var(--mac-success-strong, #34c759)',
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.12), 0 1px 2px rgba(0, 0, 0, 0.24)'
      },
      warning: {
        backgroundColor: 'var(--mac-warning-strong, var(--mac-warning))',
        color: 'white',
        border: '1px solid var(--mac-warning-strong, #ff9500)',
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.12), 0 1px 2px rgba(0, 0, 0, 0.24)'
      },
      danger: {
        backgroundColor: 'var(--mac-danger-strong, var(--mac-error))',
        color: 'white',
        border: '1px solid var(--mac-danger-strong, #ff3b30)',
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.12), 0 1px 2px rgba(0, 0, 0, 0.24)'
      },
      info: {
        backgroundColor: 'var(--mac-accent-blue-strong, var(--mac-accent-blue))',
        color: 'white',
        border: '1px solid var(--mac-accent-blue-strong, #007aff)',
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.12), 0 1px 2px rgba(0, 0, 0, 0.24)'
      }
    };

    return {
      ...baseStyles,
      ...sizeStyles[size],
      ...variantStyles[variant],
      // PR-UI-05: apply color overrides when variant is secondary
      ...(color !== 'default' && (variant === 'secondary' || !variantStyles[variant]) ? colorOverrides[color] : {}),
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



Button.displayName = 'macOS Button';

export default Button;
