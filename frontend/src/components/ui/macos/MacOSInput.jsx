import React from 'react';
import { XCircle } from 'lucide-react';

const MacOSInput = React.forwardRef(({
  className,
  style,
  icon: Icon,
  iconPosition = 'left',
  size = 'md',
  variant = 'default',
  error,
  disabled,
  clearable, // Extract to prevent passing to input
  onClear,   // Extract to prevent passing to input
  ...props
}, ref) => {
  const [isFocused, setIsFocused] = React.useState(false);
  const sizeStyles = {
    sm: {
      padding: '6px 12px',
      fontSize: 'var(--mac-font-size-sm)',
      height: '32px'
    },
    md: {
      padding: '8px 12px',
      fontSize: 'var(--mac-font-size-sm)',
      height: '36px'
    },
    lg: {
      padding: '12px 16px',
      fontSize: 'var(--mac-font-size-base)',
      height: '44px'
    }
  };

  const variantStyles = {
    default: {
      border: '1px solid var(--mac-border)',
      background: 'var(--mac-bg-primary)',
      color: 'var(--mac-text-primary)'
    },
    filled: {
      border: '1px solid transparent',
      background: 'var(--mac-bg-secondary)',
      color: 'var(--mac-text-primary)'
    },
    error: {
      border: '1px solid var(--mac-error)',
      background: 'var(--mac-bg-primary)',
      color: 'var(--mac-text-primary)'
    }
  };

  const currentVariant = error ? 'error' : variant;
  const currentSize = sizeStyles[size];
  const currentVariantStyle = variantStyles[currentVariant];

  // Determine if there is a right element taking space
  const hasRightIcon = Icon && iconPosition === 'right';
  const showClearButton = clearable && props.value && !disabled;
  let paddingRight = currentSize.padding.split(' ')[1];

  if (hasRightIcon && showClearButton) {
     paddingRight = '60px'; // Room for both
  } else if (hasRightIcon || showClearButton) {
     paddingRight = '40px'; // Room for one
  }

  const inputStyle = {
    width: '100%',
    boxSizing: 'border-box',
    paddingLeft: Icon && iconPosition === 'left' ? '40px' : currentSize.padding.split(' ')[1],
    paddingRight: paddingRight,
    paddingTop: currentSize.padding.split(' ')[0],
    paddingBottom: currentSize.padding.split(' ')[0],
    borderRadius: 'var(--mac-radius-md)',
    fontSize: currentSize.fontSize,
    height: currentSize.height,
    outline: 'none',
    transition: 'all var(--mac-duration-normal) var(--mac-ease)',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
    ...currentVariantStyle,
    ...(disabled && {
      opacity: 0.6,
      cursor: 'not-allowed',
      background: 'var(--mac-bg-tertiary)'
    }),
    ...style
  };

  const iconStyle = {
    position: 'absolute',
    top: '50%',
    transform: 'translateY(-50%)',
    color: error ? 'var(--mac-error)' : 'var(--mac-text-tertiary)',
    width: '16px',
    height: '16px',
    pointerEvents: 'none',
    ...(iconPosition === 'left' ? { left: '12px' } : { right: '12px' })
  };

  const handleFocus = (e) => {
    setIsFocused(true);
    if (!disabled) {
      e.target.style.borderColor = error ? 'var(--mac-error)' : 'var(--mac-accent-blue)';
      e.target.style.boxShadow = `0 0 0 3px ${error ? 'rgba(255, 59, 48, 0.1)' : 'rgba(0, 122, 255, 0.1)'}`;
    }
    if (props.onFocus) props.onFocus(e);
  };

  const handleBlur = (e) => {
    setIsFocused(false);
    e.target.style.borderColor = currentVariantStyle.border.split(' ')[2];
    e.target.style.boxShadow = 'none';
    if (props.onBlur) props.onBlur(e);
  };

  const clearButtonStyle = {
    position: 'absolute',
    top: '50%',
    transform: 'translateY(-50%)',
    right: hasRightIcon ? '40px' : '12px',
    background: 'none',
    border: 'none',
    padding: '2px',
    cursor: 'pointer',
    color: 'var(--mac-text-tertiary)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: '50%',
    outline: 'none',
    opacity: isFocused || props.value ? 0.7 : 0,
    transition: 'opacity 0.2s ease, color 0.2s ease',
  };

  return (
    <div style={{ position: 'relative', width: '100%' }}>
      {Icon && (
        <Icon style={iconStyle} />
      )}
      <input
        ref={ref}
        className={className}
        style={inputStyle}
        disabled={disabled}
        onFocus={handleFocus}
        onBlur={handleBlur}
        {...props}
      />
      {showClearButton && (
        <button
          type="button"
          aria-label="Clear input"
          style={clearButtonStyle}
          onClick={(e) => {
            e.stopPropagation();
            if (onClear) onClear();
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = 'var(--mac-text-secondary)';
            e.currentTarget.style.opacity = '1';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = 'var(--mac-text-tertiary)';
            e.currentTarget.style.opacity = '0.7';
          }}
          onFocus={(e) => {
            e.currentTarget.style.boxShadow = '0 0 0 2px var(--mac-accent-blue)';
            e.currentTarget.style.opacity = '1';
          }}
          onBlur={(e) => {
            e.currentTarget.style.boxShadow = 'none';
            e.currentTarget.style.opacity = '0.7';
          }}
        >
          <XCircle size={16} />
        </button>
      )}
    </div>
  );
});

MacOSInput.displayName = 'MacOSInput';

export default MacOSInput;
