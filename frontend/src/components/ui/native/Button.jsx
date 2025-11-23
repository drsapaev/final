import React from 'react';
import { useTheme } from '../../../contexts/ThemeContext';

const Button = React.forwardRef(({
  children,
  className = '',
  variant = 'default',
  size = 'md',
  disabled = false,
  loading = false,
  style = {},
  ...props
}, ref) => {
  const { getColor, getSpacing, getFontSize } = useTheme();

  const baseStyle = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: '6px',
    fontWeight: '500',
    transition: 'all 0.2s ease',
    border: 'none',
    cursor: 'pointer',
    outline: 'none',
    fontFamily: 'inherit'
  };

  const variants = {
    default: {
      backgroundColor: getColor('primary', 500),
      color: 'white',
      ':hover': {
        backgroundColor: getColor('primary', 600)
      }
    },
    destructive: {
      backgroundColor: getColor('danger', 500),
      color: 'white',
      ':hover': {
        backgroundColor: getColor('danger', 600)
      }
    },
    outline: {
      backgroundColor: 'transparent',
      color: getColor('text'),
      border: `1px solid ${getColor('border')}`,
      ':hover': {
        backgroundColor: getColor('surface')
      }
    },
    secondary: {
      backgroundColor: getColor('secondary', 500),
      color: 'white',
      ':hover': {
        backgroundColor: getColor('secondary', 600)
      }
    },
    ghost: {
      backgroundColor: 'transparent',
      color: getColor('text'),
      ':hover': {
        backgroundColor: getColor('surface')
      }
    },
    link: {
      backgroundColor: 'transparent',
      color: getColor('primary', 500),
      textDecoration: 'none',
      ':hover': {
        textDecoration: 'underline'
      }
    },
    primary: {
      backgroundColor: getColor('primary', 500),
      color: 'white',
      ':hover': {
        backgroundColor: getColor('primary', 600)
      }
    },
    success: {
      backgroundColor: getColor('success', 500),
      color: 'white',
      ':hover': {
        backgroundColor: getColor('success', 600)
      }
    },
    warning: {
      backgroundColor: getColor('warning', 500),
      color: 'white',
      ':hover': {
        backgroundColor: getColor('warning', 600)
      }
    },
    danger: {
      backgroundColor: getColor('danger', 500),
      color: 'white',
      ':hover': {
        backgroundColor: getColor('danger', 600)
      }
    }
  };

  const sizes = {
    sm: {
      height: '36px',
      padding: `${getSpacing('xs')} ${getSpacing('md')}`,
      fontSize: getFontSize('sm')
    },
    md: {
      height: '40px',
      padding: `${getSpacing('sm')} ${getSpacing('lg')}`,
      fontSize: getFontSize('base')
    },
    lg: {
      height: '44px',
      padding: `${getSpacing('sm')} ${getSpacing('xl')}`,
      fontSize: getFontSize('lg')
    },
    icon: {
      height: '40px',
      width: '40px',
      padding: getSpacing('sm')
    }
  };

  const combinedStyle = {
    ...baseStyle,
    ...sizes[size],
    ...(disabled || loading ? {
      opacity: 0.5,
      cursor: 'not-allowed',
      pointerEvents: 'none'
    } : {}),
    ...style
  };

  return (
    <button
      ref={ref}
      className={className}
      style={combinedStyle}
      disabled={disabled || loading}
      {...props}
    >
      {loading && (
        <svg
          className="animate-spin mr-2"
          style={{
            width: '16px',
            height: '16px',
            marginRight: getSpacing('sm')
          }}
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
            style={{ opacity: 0.25 }}
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            style={{ opacity: 0.75 }}
          />
        </svg>
      )}
      {children}
    </button>
  );
});

Button.displayName = 'Button';

export default Button;



