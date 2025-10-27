import React from 'react';

const MacOSRadio = React.forwardRef(({
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
  name,
  value,
  ...props
}, ref) => {
  const sizeStyles = {
    sm: {
      width: '16px',
      height: '16px',
      fontSize: 'var(--mac-font-size-xs)',
      dotSize: '6px'
    },
    md: {
      width: '20px',
      height: '20px',
      fontSize: 'var(--mac-font-size-sm)',
      dotSize: '8px'
    },
    lg: {
      width: '24px',
      height: '24px',
      fontSize: 'var(--mac-font-size-base)',
      dotSize: '10px'
    }
  };

  const variantStyles = {
    default: {
      border: '2px solid var(--mac-border)',
      background: 'var(--mac-bg-primary)',
      dotColor: 'var(--mac-accent-blue)'
    },
    filled: {
      border: '2px solid transparent',
      background: 'var(--mac-bg-secondary)',
      dotColor: 'var(--mac-accent-blue)'
    },
    error: {
      border: '2px solid var(--mac-error)',
      background: 'var(--mac-bg-primary)',
      dotColor: 'var(--mac-error)'
    }
  };

  const currentVariant = error ? 'error' : variant;
  const currentSize = sizeStyles[size];
  const currentVariantStyle = variantStyles[currentVariant];

  const radioStyle = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: '50%',
    cursor: disabled ? 'not-allowed' : 'pointer',
    transition: 'all var(--mac-duration-normal) var(--mac-ease)',
    position: 'relative',
    ...currentSize,
    border: currentVariantStyle.border,
    background: currentVariantStyle.background,
    ...(disabled && {
      opacity: 0.6
    }),
    ...style
  };

  const dotStyle = {
    width: currentSize.dotSize,
    height: currentSize.dotSize,
    borderRadius: '50%',
    background: checked ? currentVariantStyle.dotColor : 'transparent',
    transition: 'all var(--mac-duration-normal) var(--mac-ease)'
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
      onChange(value);
    }
  };

  const handleKeyDown = (e) => {
    if ((e.key === ' ' || e.key === 'Enter') && !disabled) {
      e.preventDefault();
      onChange && onChange(value);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      <div 
        style={{ display: 'flex', alignItems: 'flex-start' }}
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        tabIndex={disabled ? -1 : 0}
        role="radio"
        aria-checked={checked}
        aria-disabled={disabled}
      >
        <div
          ref={ref}
          className={className}
          style={radioStyle}
          {...props}
        >
          <div style={dotStyle} />
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

MacOSRadio.displayName = "MacOSRadio";

export default MacOSRadio;
