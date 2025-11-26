import React from 'react';
import { Check } from 'lucide-react';

const MacOSCheckbox = React.forwardRef(({
  className,
  style,
  size = 'md',
  variant = 'default',
  error,
  disabled,
  label,
  description,
  checked,
  onChange,
  ...props
}, ref) => {
  const sizeStyles = {
    sm: {
      width: '16px',
      height: '16px',
      fontSize: 'var(--mac-font-size-xs)'
    },
    md: {
      width: '20px',
      height: '20px',
      fontSize: 'var(--mac-font-size-sm)'
    },
    lg: {
      width: '24px',
      height: '24px',
      fontSize: 'var(--mac-font-size-base)'
    }
  };

  const variantStyles = {
    default: {
      border: '2px solid var(--mac-border)',
      background: checked ? 'var(--mac-accent-blue)' : 'var(--mac-bg-primary)',
      color: checked ? 'white' : 'var(--mac-text-primary)'
    },
    filled: {
      border: '2px solid transparent',
      background: checked ? 'var(--mac-accent-blue)' : 'var(--mac-bg-secondary)',
      color: checked ? 'white' : 'var(--mac-text-primary)'
    },
    error: {
      border: '2px solid var(--mac-error)',
      background: checked ? 'var(--mac-error)' : 'var(--mac-bg-primary)',
      color: checked ? 'white' : 'var(--mac-text-primary)'
    }
  };

  const currentVariant = error ? 'error' : variant;
  const currentSize = sizeStyles[size];
  const currentVariantStyle = variantStyles[currentVariant];

  const checkboxStyle = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 'var(--mac-radius-sm)',
    cursor: disabled ? 'not-allowed' : 'pointer',
    transition: 'all var(--mac-duration-normal) var(--mac-ease)',
    position: 'relative',
    ...currentSize,
    ...currentVariantStyle,
    ...(disabled && {
      opacity: 0.6
    }),
    ...style
  };

  const labelStyle = {
    marginLeft: '8px',
    fontSize: currentSize.fontSize,
    fontWeight: 'var(--mac-font-weight-medium)',
    color: disabled ? 'var(--mac-text-tertiary)' : 'var(--mac-text-primary)',
    cursor: disabled ? 'not-allowed' : 'pointer',
    userSelect: 'none'
  };

  const descriptionStyle = {
    marginLeft: '28px',
    fontSize: 'var(--mac-font-size-xs)',
    color: 'var(--mac-text-secondary)',
    marginTop: '2px',
    lineHeight: '1.4'
  };

  const handleClick = (e) => {
    if (!disabled && onChange) {
      onChange(!checked);
    }
  };

  const handleKeyDown = (e) => {
    if ((e.key === ' ' || e.key === 'Enter') && !disabled) {
      e.preventDefault();
      onChange && onChange(!checked);
    }
  };

  const iconSize = size === 'sm' ? 10 : size === 'md' ? 12 : 14;

  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      <div 
        style={{ display: 'flex', alignItems: 'flex-start' }}
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        tabIndex={disabled ? -1 : 0}
        role="checkbox"
        aria-checked={checked}
        aria-disabled={disabled}
      >
        <div
          ref={ref}
          className={className}
          style={checkboxStyle}
          {...props}
        >
          {checked && (
            <Check 
              size={iconSize} 
              style={{ 
                color: 'white',
                strokeWidth: 2.5
              }} 
            />
          )}
        </div>
        {label && (
          <label style={labelStyle}>
            {label}
          </label>
        )}
      </div>
      {description && (
        <div style={descriptionStyle}>
          {description}
        </div>
      )}
    </div>
  );
});

MacOSCheckbox.displayName = 'MacOSCheckbox';

export default MacOSCheckbox;
