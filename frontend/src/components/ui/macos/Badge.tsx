// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import React from 'react';
import PropTypes from 'prop-types';

/**
 * macOS-style Badge Component
 * Implements Apple's Human Interface Guidelines for badges and labels
 */
const Badge = React.forwardRef(({
  children,
  variant = 'default',
  size = 'default',
  className = '',
  style = {},
  ...props
}, ref) => {
  // SW-01: removed useTheme() — Badge doesn't use theme values

  // Size mapping
  const sizeMap = {
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

  const sizeStyles = sizeMap[size] || sizeMap.default;

  // Variant styles
  const variantStyles = {
    default: {
      backgroundColor: 'var(--mac-bg-tertiary)',
      color: 'var(--mac-text-primary)',
      border: '1px solid var(--mac-border)'
    },
    primary: {
      backgroundColor: 'var(--mac-accent-blue)',
      color: 'white',
      border: '1px solid var(--mac-accent-blue)'
    },
    secondary: {
      backgroundColor: 'var(--mac-bg-secondary)',
      color: 'var(--mac-text-primary)',
      border: '1px solid var(--mac-border)'
    },
    success: {
      backgroundColor: 'var(--mac-success)',
      color: 'white',
      border: '1px solid var(--mac-success)'
    },
    warning: {
      backgroundColor: 'var(--mac-warning)',
      color: 'white',
      border: '1px solid var(--mac-warning)'
    },
    danger: {
      backgroundColor: 'var(--mac-danger)',
      color: 'white',
      border: '1px solid var(--mac-danger)'
    },
    info: {
      backgroundColor: 'var(--mac-accent-blue-light)',
      color: 'white',
      border: '1px solid #5ac8fa'
    },
    outline: {
      backgroundColor: 'transparent',
      color: 'var(--mac-text-primary)',
      border: '1px solid var(--mac-border)'
    }
  };

  const badgeStyles = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: '10px',
    fontWeight: '500',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
    whiteSpace: 'nowrap',
    userSelect: 'none',
    ...sizeStyles,
    ...variantStyles[variant],
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


Badge.propTypes = {
  ...(Badge.propTypes || {}),
  children: PropTypes.any,
  className: PropTypes.any,
  size: PropTypes.any,
  style: PropTypes.any,
  variant: PropTypes.any,
};

Badge.displayName = 'macOS Badge';

export default Badge;