import React from 'react';
import { useTheme } from '../../../contexts/ThemeContext';

const Badge = React.forwardRef(({
  children,
  className = '',
  variant = 'default',
  size = 'md',
  style = {},
  ...props
}, ref) => {
  const { getColor, getSpacing, getFontSize } = useTheme();

  const baseStyle = {
    display: 'inline-flex',
    alignItems: 'center',
    borderRadius: '9999px',
    fontWeight: '600',
    transition: 'all 0.2s ease',
    border: '1px solid transparent'
  };

  const variants = {
    default: {
      backgroundColor: getColor('primary', 500),
      color: 'white',
      border: '1px solid transparent'
    },
    secondary: {
      backgroundColor: getColor('secondary', 500),
      color: 'white',
      border: '1px solid transparent'
    },
    destructive: {
      backgroundColor: getColor('danger', 500),
      color: 'white',
      border: '1px solid transparent'
    },
    outline: {
      backgroundColor: 'transparent',
      color: getColor('text'),
      border: `1px solid ${getColor('border')}`
    },
    primary: {
      backgroundColor: getColor('primary', 100),
      color: getColor('primary', 800),
      border: `1px solid ${getColor('primary', 200)}`
    },
    success: {
      backgroundColor: getColor('success', 100),
      color: getColor('success', 800),
      border: `1px solid ${getColor('success', 200)}`
    },
    warning: {
      backgroundColor: getColor('warning', 100),
      color: getColor('warning', 800),
      border: `1px solid ${getColor('warning', 200)}`
    },
    danger: {
      backgroundColor: getColor('danger', 100),
      color: getColor('danger', 800),
      border: `1px solid ${getColor('danger', 200)}`
    },
    info: {
      backgroundColor: getColor('info', 100),
      color: getColor('info', 800),
      border: `1px solid ${getColor('info', 200)}`
    },
    gray: {
      backgroundColor: getColor('secondary', 100),
      color: getColor('secondary', 800),
      border: `1px solid ${getColor('secondary', 200)}`
    }
  };

  const sizes = {
    sm: {
      padding: `${getSpacing('xs')} ${getSpacing('sm')}`,
      fontSize: getFontSize('xs')
    },
    md: {
      padding: `${getSpacing('xs')} ${getSpacing('md')}`,
      fontSize: getFontSize('xs')
    },
    lg: {
      padding: `${getSpacing('xs')} ${getSpacing('md')}`,
      fontSize: getFontSize('sm')
    }
  };

  const combinedStyle = {
    ...baseStyle,
    ...sizes[size],
    ...variants[variant],
    ...style
  };

  return (
    <div
      ref={ref}
      className={className}
      style={combinedStyle}
      {...props}
    >
      {children}
    </div>
  );
});

Badge.displayName = 'Badge';

export default Badge;



