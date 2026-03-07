import React, { useRef, useImperativeHandle, useState } from 'react';
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
  const internalRef = useRef(null);

  // Forward the internal ref to the parent
  useImperativeHandle(ref, () => internalRef.current);

  const isControlled = props.value !== undefined;
  const [internalValue, setInternalValue] = useState(props.defaultValue || '');

  const handleChange = (e) => {
    if (!isControlled) {
      setInternalValue(e.target.value);
    }
    if (props.onChange) {
      props.onChange(e);
    }
  };

  const handleClear = () => {
    if (disabled) return;

    // Create a synthetic event
    const event = Object.create(new Event('input', { bubbles: true }));
    Object.defineProperty(event, 'target', { value: { value: '' } });
    Object.defineProperty(event, 'currentTarget', { value: { value: '' } });

    // Call user defined onChange
    if (props.onChange) {
      props.onChange(event);
    }

    // Call specific onClear handler if provided
    if (onClear) {
      onClear();
    }

    // For uncontrolled inputs, we must clear the actual DOM node value
    if (!isControlled) {
      setInternalValue('');
      if (internalRef.current) {
        internalRef.current.value = '';
      }
    }

    // Refocus the input
    if (internalRef.current) {
      internalRef.current.focus();
    }
  };

  const hasValue = isControlled ? Boolean(props.value) : Boolean(internalValue);

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

  const paddingRightBase = currentSize.padding.split(' ')[1];
  let paddingRight = paddingRightBase;
  if (Icon && iconPosition === 'right') paddingRight = '40px';
  if (clearable) paddingRight = Icon && iconPosition === 'right' ? '64px' : '32px';

  const inputStyle = {
    width: '100%',
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
    ...(iconPosition === 'left' ? { left: '12px' } : { right: clearable ? '32px' : '12px' })
  };

  const clearButtonStyle = {
    position: 'absolute',
    top: '50%',
    transform: 'translateY(-50%)',
    right: '8px',
    color: 'var(--mac-text-tertiary)',
    width: '16px',
    height: '16px',
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: hasValue ? 0.6 : 0,
    pointerEvents: hasValue ? 'auto' : 'none',
    transition: 'opacity 0.2s ease, color 0.2s ease',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'none',
    border: 'none',
    padding: 0
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
        ref={internalRef}
        className={className}
        style={inputStyle}
        disabled={disabled}
        onFocus={handleFocus}
        onBlur={handleBlur}
        {...props}
        onChange={handleChange}
      />
      {clearable && (
        <button
          type="button"
          onClick={handleClear}
          style={clearButtonStyle}
          aria-label="Clear input"
          disabled={disabled}
          onMouseEnter={(e) => {
            if (!disabled && hasValue) e.currentTarget.style.color = 'var(--mac-text-primary)';
          }}
          onMouseLeave={(e) => {
            if (!disabled && hasValue) e.currentTarget.style.color = 'var(--mac-text-tertiary)';
          }}
        >
          <XCircle size={14} />
        </button>
      )}
    </div>
  );
});

MacOSInput.displayName = 'MacOSInput';

export default MacOSInput;
