import React, { type ReactNode, type CSSProperties } from 'react';
type BadgeVariant = 'default' | 'primary' | 'secondary' | 'success' | 'warning' | 'danger' | 'destructive' | 'error' | 'info' | 'outline' | string;
type BadgeSize = 'small' | 'default' | 'large' | string;

interface BadgeProps extends Omit<React.HTMLAttributes<HTMLSpanElement>, 'children' | 'style'> {
  children?: ReactNode;
  variant?: BadgeVariant;
  size?: BadgeSize;
  className?: string;
  style?: CSSProperties;
  text?: ReactNode;
  color?: string;
  outline?: boolean;
  hidden?: boolean;
}

/**
 * macOS-style Badge Component
 * Implements Apple's Human Interface Guidelines for badges and labels
 */
const Badge = React.forwardRef<HTMLSpanElement, BadgeProps>(({
  children,
  variant = 'default',
  size = 'default',
  className = '',
  style = {},
  ...props
}, ref) => {
  // SW-01: removed useTheme() — Badge doesn't use theme values

  // Size mapping
  const sizeMap: Record<string, CSSProperties> = {
    small: {
      padding: '2px 6px',
      fontSize: '10px',
      minHeight: '16px'
    },
    default: {
      padding: '4px 8px',
      fontSize: '11px',
      minHeight: '20px'
    },
    large: {
      padding: '6px 12px',
      fontSize: '13px',
      minHeight: '24px'
    }
  };

  const sizeStyles = sizeMap[size as BadgeSize] || sizeMap.default;

  // Variant styles
  // AXE-EXP-3 (authorized-surface a11y track, plan §4.1.24): the filled
  // variants carried WHITE ink on the BASE accent/status colors —
  // #007aff 4.01:1, #ff9f0a 2.05:1, #30d158 2.02:1, #ff453a 3.3:1 — all
  // below the WCAG AA 4.5:1 floor for small badge text (11px/500). Fills
  // now use the CC-2 strong-token family (--mac-*-strong, constants for
  // white ink: accent 5.42 / danger 4.85 / success 6.14 / warning 4.76).
  // The `info` variant is a soft TINT (theme-independent light blue
  // --mac-accent-blue-light ≈ #c7e2ff) — white ink on it was 1.33:1; it
  // now carries a constant dark-blue ink (#004bb5 = --mac-accent-blue-
  // active, 5.9:1 on the tint) — the tint stays light in BOTH themes, so
  // the ink must be theme-independent dark too (a themed --mac-text-*
  // ink would flip to white in dark and fail again).
  const variantStyles: Record<string, CSSProperties> = {
    default: {
      backgroundColor: 'var(--mac-bg-tertiary)',
      color: 'var(--mac-text-primary)',
      border: '1px solid var(--mac-border)'
    },
    primary: {
      backgroundColor: 'var(--mac-accent-blue-strong, var(--mac-accent-blue))',
      color: 'white',
      border: '1px solid var(--mac-accent-blue-strong, var(--mac-accent-blue))'
    },
    secondary: {
      backgroundColor: 'var(--mac-bg-secondary)',
      color: 'var(--mac-text-primary)',
      border: '1px solid var(--mac-border)'
    },
    success: {
      backgroundColor: 'var(--mac-success-strong, var(--mac-success))',
      color: 'white',
      border: '1px solid var(--mac-success-strong, var(--mac-success))'
    },
    warning: {
      backgroundColor: 'var(--mac-warning-strong, var(--mac-warning))',
      color: 'white',
      border: '1px solid var(--mac-warning-strong, var(--mac-warning))'
    },
    danger: {
      backgroundColor: 'var(--mac-danger-strong, var(--mac-danger))',
      color: 'white',
      border: '1px solid var(--mac-danger-strong, var(--mac-danger))'
    },
    info: {
      backgroundColor: 'var(--mac-accent-blue-light)',
      color: 'var(--mac-accent-blue-active, #004bb5)',
      border: '1px solid #5ac8fa'
    },
    outline: {
      backgroundColor: 'transparent',
      color: 'var(--mac-text-primary)',
      border: '1px solid var(--mac-border)'
    }
  };

  const badgeStyles: CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: '10px',
    fontWeight: '500',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
    whiteSpace: 'nowrap',
    userSelect: 'none',
    ...sizeStyles,
    ...(variantStyles[variant as BadgeVariant] || variantStyles.default),
    ...style
  };

  return (
    <span
      ref={ref}
      className={`mac-badge ${className}`}
      style={badgeStyles}
      {...props}>

      {children}
    </span>);

});



Badge.displayName = 'macOS Badge';

export default Badge;
