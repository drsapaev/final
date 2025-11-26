import React from 'react';

const MacOSSelect = React.forwardRef(({
  className,
  style,
  options = [],
  size = 'md',
  variant = 'default',
  error,
  disabled,
  placeholder,
  ...props
}, ref) => {
  const sizeStyles = {
    sm: {
      padding: '6px 32px 6px 12px',
      fontSize: 'var(--mac-font-size-sm)',
      height: '32px'
    },
    md: {
      padding: '8px 32px 8px 12px',
      fontSize: 'var(--mac-font-size-sm)',
      height: '36px'
    },
    lg: {
      padding: '12px 40px 12px 16px',
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

  const selectStyle = {
    width: '100%',
    borderRadius: 'var(--mac-radius-md)',
    fontSize: currentSize.fontSize,
    height: currentSize.height,
    outline: 'none',
    transition: 'all var(--mac-duration-normal) var(--mac-ease)',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
    WebkitAppearance: 'none',
    MozAppearance: 'none',
    appearance: 'none',
    backgroundImage: 'url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 20 20\' fill=\'none\' stroke=\'%236B7280\' stroke-width=\'1.5\' stroke-linecap=\'round\' stroke-linejoin=\'round\'%3E%3Cpolyline points=\'6 9 12 15 18 9\'%3E%3C/polyline%3E%3C/svg%3E")',
    backgroundRepeat: 'no-repeat',
    backgroundPosition: 'right 12px center',
    backgroundSize: '12px',
    cursor: disabled ? 'not-allowed' : 'pointer',
    ...currentSize,
    ...currentVariantStyle,
    ...(disabled && {
      opacity: 0.6,
      background: 'var(--mac-bg-tertiary)'
    }),
    ...style
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

  // Извлекаем onChange из props, чтобы убедиться, что он передается
  const { onChange, ...restProps } = props;

  const handleChange = (e) => {
    if (onChange) {
      onChange(e);
    }
  };

  return (
    <select
      ref={ref}
      className={className}
      style={selectStyle}
      disabled={disabled}
      onFocus={handleFocus}
      onBlur={handleBlur}
      onChange={handleChange}
      {...restProps}
    >
      {placeholder && (
        <option value="" disabled>
          {placeholder}
        </option>
      )}
      {options && options.length > 0 ? (
        options.map((option) => (
          <option
            key={option.value || option}
            value={option.value || option}
            disabled={option.disabled}
          >
            {option.label || option}
          </option>
        ))
      ) : (
        // Поддержка children для совместимости с обычным select
        props.children || (
          <>
            <option value="ru">RU</option>
            <option value="uz">UZ</option>
            <option value="en">EN</option>
            <option value="kk">KK</option>
          </>
        )
      )}
    </select>
  );
});

MacOSSelect.displayName = 'MacOSSelect';

export default MacOSSelect;