import React, { useState, useRef, useEffect } from 'react';
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
  clearable,
  onClear,
  onChange,
  onInput,
  value,
  defaultValue,
  ...props
}, ref) => {
  const isControlled = value !== undefined;
  const [internalValue, setInternalValue] = useState(defaultValue || '');
  const currentValue = isControlled ? value : internalValue;
  const hasValue = Boolean(currentValue);

  const internalRef = useRef(null);

  const setRefs = (node) => {
    internalRef.current = node;
    if (typeof ref === 'function') {
      ref(node);
    } else if (ref) {
      ref.current = node;
    }
  };

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

  const inputStyle = {
    width: '100%',
    paddingLeft: Icon && iconPosition === 'left' ? '40px' : currentSize.padding.split(' ')[1],
    paddingRight: (Icon && iconPosition === 'right' ? 40 : parseInt(currentSize.padding.split(' ')[1])) + (clearable ? 24 : 0) + 'px',
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

  const clearButtonStyle = {
    position: 'absolute',
    right: Icon && iconPosition === 'right' ? '36px' : '12px',
    top: '50%',
    transform: 'translateY(-50%)',
    background: 'none',
    border: 'none',
    padding: '4px',
    cursor: 'pointer',
    color: 'var(--mac-text-tertiary)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    opacity: 0.7,
    transition: 'opacity var(--mac-duration-normal) var(--mac-ease)',
    borderRadius: '50%',
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

  const handleChange = (e) => {
    if (!isControlled) {
      setInternalValue(e.target.value);
    }
    if (onChange) onChange(e);
  };

  const handleInput = (e) => {
    if (!isControlled) {
      setInternalValue(e.target.value);
    }
    if (onInput) onInput(e);
  };

  const handleClear = (e) => {
    e.preventDefault();

    if (internalRef.current) {
      const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype,
        'value'
      )?.set;

      if (nativeInputValueSetter) {
        nativeInputValueSetter.call(internalRef.current, '');
      } else {
        internalRef.current.value = '';
      }

      const event = new Event('input', { bubbles: true });
      const changeEvent = new Event('change', { bubbles: true });

      internalRef.current.dispatchEvent(event);
      internalRef.current.dispatchEvent(changeEvent);
    }

    if (!isControlled) {
      setInternalValue('');
    }

    if (onClear) onClear();
    internalRef.current?.focus();
  };

  return (
    <div style={{ position: 'relative', width: '100%' }}>
      {Icon && iconPosition === 'left' && (
        <Icon style={iconStyle} />
      )}
      <input
        ref={setRefs}
        className={className}
        style={inputStyle}
        disabled={disabled}
        onFocus={handleFocus}
        onBlur={handleBlur}
        onChange={handleChange}
        onInput={handleInput}
        value={value}
        defaultValue={defaultValue}
        {...props}
      />
      {clearable && hasValue && !disabled && (
        <button
          type="button"
          onClick={handleClear}
          style={clearButtonStyle}
          onMouseEnter={(e) => e.currentTarget.style.opacity = '1'}
          onMouseLeave={(e) => e.currentTarget.style.opacity = '0.7'}
          aria-label="Clear input"
        >
          <XCircle size={14} />
        </button>
      )}
      {Icon && iconPosition === 'right' && (
        <Icon style={iconStyle} />
      )}
    </div>
  );
});

MacOSInput.displayName = 'MacOSInput';

export default MacOSInput;
