import React from 'react';

/**
 * macOS-style Option Component
 * Simple option component for Select dropdowns
 */
const Option = React.forwardRef(({
  children,
  value,
  disabled = false,
  className = '',
  style = {},
  ...props
}, ref) => {
  const optionStyles = {
    padding: '8px 12px',
    fontSize: '13px',
    color: disabled ? 'var(--mac-text-disabled)' : 'var(--mac-text-primary)',
    backgroundColor: 'transparent',
    border: 'none',
    cursor: disabled ? 'not-allowed' : 'pointer',
    transition: 'background-color 0.2s ease',
    ...style
  };

  const handleMouseEnter = (e) => {
    if (!disabled) {
      e.target.style.backgroundColor = 'var(--mac-bg-secondary)';
    }
  };

  const handleMouseLeave = (e) => {
    if (!disabled) {
      e.target.style.backgroundColor = 'transparent';
    }
  };

  return (
    <option
      ref={ref}
      value={value}
      disabled={disabled}
      className={`mac-option ${disabled ? 'mac-option--disabled' : ''} ${className}`}
      style={optionStyles}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      {...props}
    >
      {children}
    </option>
  );
});

Option.displayName = 'Option';

export default Option;
