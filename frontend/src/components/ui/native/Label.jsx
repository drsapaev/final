import React from 'react';
import { cn } from '../../../utils/cn';
import PropTypes from 'prop-types';

const Label = React.forwardRef(({ 
  children,
  className = '', 
  variant = 'default',
  size = 'md',
  required = false,
  ...props 
}, ref) => {
  const baseClasses = 'text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70';
  
  const variants = {
    default: 'text-gray-700',
    muted: 'text-gray-500',
    error: 'text-red-600'
  };
  
  const sizes = {
    sm: 'text-xs',
    md: 'text-sm',
    lg: 'text-base'
  };
  
  return (
    <label
      ref={ref}
      className={cn(
        baseClasses,
        variants[variant],
        sizes[size],
        className
      )}
      {...props}
    >
      {children}
      {required && <span className="text-red-500 ml-1">*</span>}
    </label>
  );
});


Label.propTypes = {
  ...(Label.propTypes || {}),
  children: PropTypes.any,
  className: PropTypes.any,
  required: PropTypes.any,
  size: PropTypes.any,
  variant: PropTypes.any,
};

Label.displayName = 'Label';

export default Label;



