import React, { useEffect, useRef } from 'react';

const MacOSTextarea = React.forwardRef(({
  className,
  style,
  size = 'md',
  variant = 'default',
  error,
  disabled,
  autoResize = true,
  minRows = 3,
  maxRows = 10,
  ...props
}, ref) => {
  const textareaRef = useRef(null);
  const internalRef = ref || textareaRef;

  const sizeStyles = {
    sm: {
      padding: '8px 12px',
      fontSize: 'var(--mac-font-size-sm)',
      lineHeight: '1.4'
    },
    md: {
      padding: '12px 16px',
      fontSize: 'var(--mac-font-size-sm)',
      lineHeight: '1.5'
    },
    lg: {
      padding: '16px 20px',
      fontSize: 'var(--mac-font-size-base)',
      lineHeight: '1.6'
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

  const textareaStyle = {
    width: '100%',
    borderRadius: 'var(--mac-radius-md)',
    fontSize: currentSize.fontSize,
    lineHeight: currentSize.lineHeight,
    outline: 'none',
    transition: 'all var(--mac-duration-normal) var(--mac-ease)',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
    resize: autoResize ? 'none' : 'vertical',
    overflow: autoResize ? 'hidden' : 'auto',
    ...currentSize,
    ...currentVariantStyle,
    ...(disabled && {
      opacity: 0.6,
      cursor: 'not-allowed',
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

  const adjustHeight = () => {
    if (autoResize && internalRef.current) {
      const textarea = internalRef.current;
      textarea.style.height = 'auto';
      
      const scrollHeight = textarea.scrollHeight;
      const lineHeight = parseInt(currentSize.lineHeight) * parseInt(currentSize.fontSize);
      const minHeight = lineHeight * minRows;
      const maxHeight = lineHeight * maxRows;
      
      const newHeight = Math.min(Math.max(scrollHeight, minHeight), maxHeight);
      textarea.style.height = `${newHeight}px`;
    }
  };

  useEffect(() => {
    if (autoResize) {
      adjustHeight();
    }
  }, [props.value, props.defaultValue]);

  return (
    <textarea
      ref={internalRef}
      className={className}
      style={textareaStyle}
      disabled={disabled}
      onFocus={handleFocus}
      onBlur={handleBlur}
      onInput={adjustHeight}
      rows={minRows}
      {...props}
    />
  );
});

MacOSTextarea.displayName = 'MacOSTextarea';

export default MacOSTextarea;
