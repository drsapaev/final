import React, { forwardRef } from 'react';
import { createButtonStyles } from './utils';
import { SIZES, VARIANTS } from './types';

const Button = forwardRef(({
  children,
  variant = VARIANTS.PRIMARY,
  size = SIZES.MD,
  disabled = false,
  loading = false,
  fullWidth = false,
  className = '',
  style = {},
  onClick,
  onMouseEnter,
  onMouseLeave,
  ...props
}, ref) => {
  const buttonStyles = createButtonStyles(variant, size, disabled || loading);
  
  const finalStyles = {
    ...buttonStyles,
    width: fullWidth ? '100%' : 'auto',
    ...style
  };

  const handleClick = (e) => {
    if (!disabled && !loading && onClick) {
      onClick(e);
    }
  };

  const handleMouseEnter = (e) => {
    if (!disabled && !loading && onMouseEnter) {
      onMouseEnter(e);
    }
  };

  const handleMouseLeave = (e) => {
    if (!disabled && !loading && onMouseLeave) {
      onMouseLeave(e);
    }
  };

  return (
    <button
      ref={ref}
      className={`design-system-button ${className}`}
      style={finalStyles}
      disabled={disabled || loading}
      onClick={handleClick}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      {...props}
    >
      {loading && (
        <div
          style={{
            width: '16px',
            height: '16px',
            border: '2px solid transparent',
            borderTop: '2px solid currentColor',
            borderRadius: '50%',
            animation: 'spin 1s linear infinite',
            marginRight: '8px'
          }}
        />
      )}
      {children}
    </button>
  );
});

Button.displayName = 'Button';

export default Button;
