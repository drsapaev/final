import React, { type ReactNode, type CSSProperties } from 'react';
import PropTypes from 'prop-types';

interface OptionProps extends Omit<React.OptionHTMLAttributes<HTMLOptionElement>, 'children'> {
  children?: ReactNode;
  disabled?: boolean;
  className?: string;
  style?: CSSProperties;
}

interface OptionStyles extends CSSProperties {
  transition?: string;
}

/**
 * macOS-style Option Component
 * Simple option component for Select dropdowns
 */
const Option = React.forwardRef<HTMLOptionElement, OptionProps>(({
  children,
  value,
  disabled = false,
  className = '',
  style = {},
  ...props
}, ref) => {
  const optionStyles: OptionStyles = {
    padding: '8px 12px',
    fontSize: '13px',
    color: disabled ? 'var(--mac-text-disabled)' : 'var(--mac-text-primary)',
    backgroundColor: 'transparent',
    border: 'none',
    cursor: disabled ? 'not-allowed' : 'pointer',
    transition: 'background-color 0.2s ease',
    ...style
  };

  const handleMouseEnter = (e: React.MouseEvent<HTMLOptionElement>) => {
    if (!disabled) {
      e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)';
    }
  };

  const handleMouseLeave = (e: React.MouseEvent<HTMLOptionElement>) => {
    if (!disabled) {
      e.currentTarget.style.backgroundColor = 'transparent';
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


Option.propTypes = {
  ...(Option.propTypes || {}),
  children: PropTypes.any,
  className: PropTypes.any,
  disabled: PropTypes.any,
  style: PropTypes.any,
  value: PropTypes.any,
};

Option.displayName = 'Option';

export default Option;
