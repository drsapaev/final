import React, { useRef, useImperativeHandle } from 'react';
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

  useImperativeHandle(ref, () => internalRef.current);

  const isControlled = props.value !== undefined;
  const [uncontrolledValue, setUncontrolledValue] = React.useState(props.defaultValue || '');
  const currentValue = isControlled ? props.value : uncontrolledValue;

  const hasValue = currentValue !== undefined && currentValue !== null && currentValue !== '';

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

  const paddingLeft = Icon && iconPosition === 'left' ? '40px' : currentSize.padding.split(' ')[1];

  let paddingRight = currentSize.padding.split(' ')[1];
  if (clearable) {
    paddingRight = '32px';
  } else if (Icon && iconPosition === 'right') {
    paddingRight = '40px';
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

  const handleChange = (e) => {
    if (!isControlled) {
      setUncontrolledValue(e.target.value);
    }
    if (props.onChange) {
      props.onChange(e);
    }
  };

  const handleClear = (e) => {
    e.preventDefault();
    e.stopPropagation();

    if (!isControlled) {
      setUncontrolledValue('');
    }

    // Ensure the underlying DOM node is updated so that an onChange event fires properly
    if (internalRef.current) {
      const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype,
        'value'
      ).set;
      nativeInputValueSetter.call(internalRef.current, '');
      const event = new Event('input', { bubbles: true });
      internalRef.current.dispatchEvent(event);
    }

    if (onClear) {
      onClear();
    }

    // Maintain focus after clearing
    internalRef.current?.focus();
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
        onChange={handleChange}
        {...props}
      />
      {clearable && hasValue && !disabled && (
        <button
          type="button"
          onClick={handleClear}
          aria-label="Clear input"
          style={{
            position: 'absolute',
            right: '8px',
            top: '50%',
            transform: 'translateY(-50%)',
            background: 'none',
            border: 'none',
            padding: '2px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            color: 'var(--mac-text-tertiary)',
            borderRadius: '50%'
          }}
          onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--mac-text-secondary)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--mac-text-tertiary)'; }}
        >
          <XCircle size={14} />
        </button>
      )}
    </div>
  );
});

MacOSInput.displayName = 'MacOSInput';

export default MacOSInput;
