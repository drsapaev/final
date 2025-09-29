import React from 'react';
import { cn } from '../../../utils/cn';

const Textarea = React.forwardRef(({ 
  className = '', 
  variant = 'default',
  size = 'md',
  error = false,
  resize = 'vertical',
  ...props 
}, ref) => {
  const baseClasses = 'flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50';
  
  const variants = {
    default: 'border-gray-300 focus:border-blue-500 focus:ring-blue-500',
    filled: 'bg-gray-100 border-gray-300 focus:bg-white focus:border-blue-500'
  };
  
  const sizes = {
    sm: 'min-h-[60px] px-2 py-1 text-sm',
    md: 'min-h-[80px] px-3 py-2',
    lg: 'min-h-[120px] px-4 py-3 text-lg'
  };
  
  const resizeClasses = {
    none: 'resize-none',
    vertical: 'resize-y',
    horizontal: 'resize-x',
    both: 'resize'
  };
  
  return (
    <textarea
      ref={ref}
      className={cn(
        baseClasses,
        variants[variant],
        sizes[size],
        resizeClasses[resize],
        error && 'border-red-500 focus:border-red-500 focus:ring-red-500',
        className
      )}
      {...props}
    />
  );
});

Textarea.displayName = 'Textarea';

export default Textarea;



