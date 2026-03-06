import React from 'react';
import { X } from 'lucide-react';

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
  value,
  ...props
}, ref) => {
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

  const hasClearButton = clearable && !disabled && value && String(value).length > 0;

  // Calculate padding based on icons present
  let paddingLeft = currentSize.padding.split(' ')[1];
  let paddingRight = currentSize.padding.split(' ')[1];

  if (Icon && iconPosition === 'left') {
    paddingLeft = '40px';
  }

  if (Icon && iconPosition === 'right') {
    paddingRight = '40px';
  }

  // Add extra padding for clear button if present (it appears on the right)
  if (hasClearButton) {
    // If there's already an icon on the right, push padding further
    if (Icon && iconPosition === 'right') {
      paddingRight = '68px'; // 40px (icon) + 28px (clear button)
    } else {
      paddingRight = '36px'; // Standard padding for clear button
    }
  }

  const inputStyle = {
    width: '100%',
    paddingLeft,
    paddingRight,
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
    if (!disabled) {
      e.target.style.borderColor = error ? 'var(--mac-error)' : 'var(--mac-accent-blue)';
      e.target.style.boxShadow = `0 0 0 3px ${error ? 'rgba(255, 59, 48, 0.1)' : 'rgba(0, 122, 255, 0.1)'}`;
    }
  };

  const handleBlur = (e) => {
    e.target.style.borderColor = currentVariantStyle.border.split(' ')[2];
    e.target.style.boxShadow = 'none';
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
        value={value}
        {...props}
      />
      {hasClearButton && (
        <button
          type="button"
          onClick={onClear}
          onMouseDown={(e) => e.preventDefault()} // Prevent focus loss
          style={{
            position: 'absolute',
            right: Icon && iconPosition === 'right' ? '40px' : '8px',
            top: '50%',
            transform: 'translateY(-50%)',
            border: 'none',
            background: 'transparent',
            color: 'var(--mac-text-tertiary)',
            cursor: 'pointer',
            padding: '4px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: '50%',
            transition: 'color 0.2s ease, background-color 0.2s ease'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = 'var(--mac-text-secondary)';
            e.currentTarget.style.backgroundColor = 'var(--mac-bg-tertiary)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = 'var(--mac-text-tertiary)';
            e.currentTarget.style.backgroundColor = 'transparent';
          }}
          aria-label="Clear input"
        >
          <X size={14} />
        </button>
      )}
    </div>
  );
});

MacOSInput.displayName = 'MacOSInput';

export default MacOSInput;
