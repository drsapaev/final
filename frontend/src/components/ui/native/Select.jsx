import React from 'react';
import { cn } from '../../../utils/cn';

const Select = React.forwardRef(({ 
  children,
  className = '', 
  variant = 'default',
  size = 'md',
  error = false,
  ...props 
}, ref) => {
  const baseClasses = 'flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50';
  
  const variants = {
    default: 'border-gray-300 focus:border-blue-500 focus:ring-blue-500',
    filled: 'bg-gray-100 border-gray-300 focus:bg-white focus:border-blue-500'
  };
  
  const sizes = {
    sm: 'h-8 px-2 text-sm',
    md: 'h-10 px-3',
    lg: 'h-12 px-4 text-lg'
  };
  
  return (
    <select
      ref={ref}
      className={cn(
        baseClasses,
        variants[variant],
        sizes[size],
        error && 'border-red-500 focus:border-red-500 focus:ring-red-500',
        className
      )}
      {...props}
    >
      {children}
    </select>
  );
});

Select.displayName = 'Select';

const Option = React.forwardRef(({ 
  children,
  className = '', 
  ...props 
}, ref) => (
  <option
    ref={ref}
    className={cn('py-2 px-3', className)}
    {...props}
  >
    {children}
  </option>
));

Option.displayName = 'Option';

export default Select;
export { Option };



