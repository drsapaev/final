// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import React from 'react';
import PropTypes from 'prop-types';

const Label = React.forwardRef(({ 
  children,
  className = '', 
  variant = 'default',
  size = 'md',
  required = false,
  style = {},
  ...props 
}, ref) => {
  const baseStyles = {
    fontSize: '14px',
    fontWeight: '500',
    lineHeight: '1',
    cursor: 'pointer',
    transition: 'color var(--mac-duration-normal) var(--mac-ease)'
  };
  
  const variants = {
    default: { color: 'var(--mac-text-primary)' },
    muted: { color: 'var(--mac-text-secondary)' },
    error: { color: 'var(--mac-error)' }
  };
  
  const sizes = {
    sm: { fontSize: '12px' },
    md: { fontSize: '14px' },
    lg: { fontSize: '16px' }
  };
  
  const labelStyles = {
    ...baseStyles,
    ...variants[variant],
    ...sizes[size],
    ...style
  };
  
  return (
    <label
      ref={ref}
      style={labelStyles}
      className={className}
      {...props}
    >
      {children}
      {required && (
        <span style={{ color: 'var(--mac-error)', marginLeft: '4px' }}>
          *
        </span>
      )}
    </label>
  );
});


Label.propTypes = {
  ...(Label.propTypes || {}),
  children: PropTypes.any,
  className: PropTypes.any,
  required: PropTypes.any,
  size: PropTypes.any,
  style: PropTypes.any,
  variant: PropTypes.any,
};

Label.displayName = 'Label';

export default Label;
