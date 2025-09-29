import React from 'react';
import { cn } from '../../../utils/cn';

const Input = React.forwardRef(({ 
  className = '', 
  type = 'text',
  variant = 'default',
  size = 'md',
  error = false,
  ...props 
}, ref) => {
  const baseClasses = 'flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50';
  
  const variants = {
    default: 'border-gray-300 focus:border-blue-500 focus:ring-blue-500',
    filled: 'bg-gray-100 border-gray-300 focus:bg-white focus:border-blue-500',
    underlined: 'border-0 border-b-2 border-gray-300 rounded-none focus:border-blue-500 bg-transparent'
  };
  
  const sizes = {
    sm: 'h-8 px-2 text-sm',
    md: 'h-10 px-3',
    lg: 'h-12 px-4 text-lg'
  };
  
  return (
    <input
      ref={ref}
      type={type}
      className={cn(
        baseClasses,
        variants[variant],
        sizes[size],
        error && 'border-red-500 focus:border-red-500 focus:ring-red-500',
        className
      )}
      {...props}
    />
  );
});

Input.displayName = 'Input';

export default Input;



