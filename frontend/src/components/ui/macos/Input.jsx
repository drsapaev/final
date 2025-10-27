import React, { useState } from 'react';
import { useTheme } from '../../../contexts/ThemeContext';

/**
 * macOS-style Input Component
 * Implements Apple's Human Interface Guidelines for text inputs
 */
const Input = React.forwardRef(({
  type = 'text',
  variant = 'default',
  size = 'default',
  error = false,
  disabled = false,
  placeholder,
  value,
  onChange,
  onFocus,
  onBlur,
  className = '',
  style = {},
  label,
  hint,
  ...props
}, ref) => {
  const { theme } = useTheme();
  const [isFocused, setIsFocused] = useState(false);

  // macOS input styles based on variant and state
  const getInputStyles = () => {
    const baseStyles = {
      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
      fontSize: '13px',
      fontWeight: '400',
      borderRadius: '6px',
      border: `1px solid ${error ? '#ff3b30' : isFocused ? '#007aff' : 'var(--mac-border)'}`,
      backgroundColor: disabled ? 'var(--mac-bg-tertiary)' : 'var(--mac-bg-primary)',
      color: 'var(--mac-text-primary)',
      padding: '8px 12px',
      transition: 'all 0.2s cubic-bezier(0.2, 0.8, 0.2, 1)',
      outline: 'none',
      WebkitAppearance: 'none',
      MozAppearance: 'none',
      appearance: 'none',
      backdropFilter: 'blur(10px)',
      position: 'relative'
    };

    // Focus ring effect
    if (isFocused && !error) {
      baseStyles.boxShadow = '0 0 0 3px rgba(0, 122, 255, 0.1)';
    }

    // Error state
    if (error) {
      baseStyles.borderColor = '#ff3b30';
      baseStyles.boxShadow = '0 0 0 3px rgba(255, 59, 48, 0.1)';
    }

    // Disabled state
    if (disabled) {
      baseStyles.opacity = 0.5;
      baseStyles.cursor = 'not-allowed';
    }

    return {
      ...baseStyles,
      ...style
    };
  };

  const handleFocus = (e) => {
    setIsFocused(true);
    if (onFocus) onFocus(e);
  };

  const handleBlur = (e) => {
    setIsFocused(false);
    if (onBlur) onBlur(e);
  };

  const inputStyles = getInputStyles();

  return (
    <div className={`mac-input-wrapper ${className}`} style={{ position: 'relative' }}>
      {/* Label */}
      {label && (
        <label
          className="mac-input-label"
          style={{
            display: 'block',
            fontSize: '13px',
            fontWeight: '500',
            color: error ? '#ff3b30' : 'var(--mac-text-secondary)',
            marginBottom: '4px',
            fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif'
          }}
        >
          {label}
          {props.required && <span style={{ color: '#ff3b30', marginLeft: '2px' }}>*</span>}
        </label>
      )}

      {/* Input field */}
      <input
        ref={ref}
        type={type}
        value={value}
        onChange={onChange}
        onFocus={handleFocus}
        onBlur={handleBlur}
        disabled={disabled}
        placeholder={placeholder}
        className="mac-input"
        style={inputStyles}
        {...props}
      />

      {/* Hint text */}
      {hint && (
        <div
          className="mac-input-hint"
          style={{
            fontSize: '11px',
            color: 'var(--mac-text-tertiary)',
            marginTop: '4px',
            fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif'
          }}
        >
          {hint}
        </div>
      )}

      {/* Error message */}
      {error && (
        <div
          className="mac-input-error"
          style={{
            fontSize: '11px',
            color: '#ff3b30',
            marginTop: '4px',
            fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif'
          }}
        >
          {error}
        </div>
      )}

      {/* Focus indicator */}
      {isFocused && !error && (
        <div
          className="mac-input-focus-indicator"
          style={{
            position: 'absolute',
            top: '-1px',
            left: '-1px',
            right: '-1px',
            bottom: '-1px',
            border: '2px solid #007aff',
            borderRadius: '7px',
            pointerEvents: 'none',
            zIndex: 1
          }}
        />
      )}
    </div>
  );
});

Input.displayName = 'macOS Input';

export default Input;

