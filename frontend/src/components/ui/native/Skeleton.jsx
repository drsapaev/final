import React from 'react';
import { cn } from '../../../utils/cn';

const Skeleton = React.forwardRef(({ 
  className = '', 
  variant = 'default',
  ...props 
}, ref) => {
  const baseClasses = 'animate-pulse rounded-md bg-muted';
  
  const variants = {
    default: 'bg-gray-200',
    text: 'h-4 bg-gray-200',
    avatar: 'h-12 w-12 rounded-full bg-gray-200',
    button: 'h-10 w-20 bg-gray-200',
    card: 'h-32 w-full bg-gray-200',
    line: 'h-4 w-full bg-gray-200',
    circle: 'rounded-full bg-gray-200'
  };
  
  return (
    <div
      ref={ref}
      className={cn(
        baseClasses,
        variants[variant],
        className
      )}
      {...props}
    />
  );
});

Skeleton.displayName = 'Skeleton';

export default Skeleton;



