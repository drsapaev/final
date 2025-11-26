import React, { useState, useEffect, useRef } from 'react';

const Textarea = React.forwardRef(({ 
  value: valueProp,
  defaultValue = '',
  onChange,
  onFocus,
  onBlur,
  placeholder,
  disabled = false,
  error = false,
  size = 'default',
  variant = 'default',
  label,
  hint,
  maxLength,
  minRows = 3,
  maxRows = 10,
  autoResize = true,
  className = '',
  style = {},
  id,
  ...props
}, ref) => {
  const [value, setValue] = useState(valueProp ?? defaultValue);
  const [isFocused, setIsFocused] = useState(false);
  const textareaRef = useRef(null);
  const controlId = id || `textarea_${Math.random().toString(36).slice(2)}`;

  useEffect(() => {
    if (valueProp !== undefined) setValue(valueProp);
  }, [valueProp]);

  useEffect(() => {
    if (autoResize && textareaRef.current) {
      const textarea = textareaRef.current;
      textarea.style.height = 'auto';
      const scrollHeight = textarea.scrollHeight;
      const lineHeight = parseInt(getComputedStyle(textarea).lineHeight) || 20;
      const minHeight = minRows * lineHeight;
      const maxHeight = maxRows * lineHeight;
      const newHeight = Math.min(Math.max(scrollHeight, minHeight), maxHeight);
      textarea.style.height = `${newHeight}px`;
    }
  }, [value, autoResize, minRows, maxRows]);

  const sizes = {
    small: { fontSize: 12, padding: '6px 8px', borderRadius: '6px' },
    default: { fontSize: 13, padding: '8px 10px', borderRadius: '8px' },
    large: { fontSize: 14, padding: '10px 12px', borderRadius: '10px' }
  };

  const s = sizes[size] || sizes.default;

  const handleChange = (e) => {
    const newValue = e.target.value;
    if (valueProp === undefined) setValue(newValue);
    onChange && onChange(e);
  };

  const handleFocus = (e) => {
    setIsFocused(true);
    onFocus && onFocus(e);
  };

  const handleBlur = (e) => {
    setIsFocused(false);
    onBlur && onBlur(e);
  };

  const wrapperStyles = {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    ...style
  };

  const labelStyles = {
    fontSize: '12px',
    color: 'var(--mac-text-secondary)',
    fontWeight: '500'
  };

  const textareaStyles = {
    width: '100%',
    fontSize: `${s.fontSize}px`,
    padding: s.padding,
    borderRadius: s.borderRadius,
    border: '1px solid var(--mac-border)',
    background: disabled ? 'var(--mac-bg-tertiary)' : 'var(--mac-bg-elev-1)',
    color: 'var(--mac-text-primary)',
    fontFamily: 'inherit',
    lineHeight: '1.4',
    resize: autoResize ? 'none' : 'vertical',
    outline: 'none',
    transition: 'all 160ms cubic-bezier(0.2,0.8,0.2,1)',
    boxShadow: 'var(--mac-shadow-1)',
    cursor: disabled ? 'not-allowed' : 'text',
    opacity: disabled ? 0.6 : 1
  };

  const focusStyles = isFocused ? {
    border: '1px solid var(--mac-accent-blue-500)',
    boxShadow: '0 0 0 2px color-mix(in srgb, var(--mac-accent-blue-500), transparent 70%)'
  } : {};

  const errorStyles = error ? {
    border: '1px solid var(--mac-danger-500)',
    boxShadow: '0 0 0 2px color-mix(in srgb, var(--mac-danger-500), transparent 70%)'
  } : {};

  const hintStyles = {
    fontSize: '11px',
    color: 'var(--mac-text-secondary)',
    marginTop: '2px'
  };

  const errorTextStyles = {
    fontSize: '11px',
    color: 'var(--mac-danger-600)',
    marginTop: '2px'
  };

  const characterCountStyles = {
    fontSize: '11px',
    color: 'var(--mac-text-tertiary)',
    textAlign: 'right',
    marginTop: '2px'
  };

  const getCharacterCount = () => {
    if (!maxLength) return null;
    return `${value.length}/${maxLength}`;
  };

  return (
    <div className={`mac-textarea-wrapper ${className}`} style={wrapperStyles}>
      {label && (
        <label htmlFor={controlId} style={labelStyles}>
          {label}
        </label>
      )}
      
      <textarea
        ref={(node) => {
          textareaRef.current = node;
          if (typeof ref === 'function') ref(node);
          else if (ref) ref.current = node;
        }}
        id={controlId}
        value={value}
        onChange={handleChange}
        onFocus={handleFocus}
        onBlur={handleBlur}
        placeholder={placeholder}
        disabled={disabled}
        maxLength={maxLength}
        rows={minRows}
        className="mac-textarea"
        style={{
          ...textareaStyles,
          ...focusStyles,
          ...errorStyles
        }}
        {...props}
      />
      
      {isFocused && !error && (
        <div 
          className="mac-textarea-focus-indicator"
          style={{
            position: 'absolute',
            top: '1px',
            left: '1px',
            right: '1px',
            bottom: '1px',
            borderRadius: s.borderRadius,
            border: '1px solid var(--mac-accent-blue-500)',
            pointerEvents: 'none',
            zIndex: 1
          }}
        />
      )}
      
      {hint && !error && (
        <div style={hintStyles}>
          {hint}
        </div>
      )}
      
      {error && (
        <div className="mac-textarea-error" role="alert" style={errorTextStyles}>
          {error}
        </div>
      )}
      
      {maxLength && (
        <div style={characterCountStyles}>
          {getCharacterCount()}
        </div>
      )}
    </div>
  );
});

export default Textarea;
