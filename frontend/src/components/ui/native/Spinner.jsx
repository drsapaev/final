import React from 'react';
import { cn } from '../../../utils/cn';

const Spinner = React.forwardRef(({ 
  size = 'md',
  color = 'primary',
  className = '',
  ...props 
}, ref) => {
  const sizes = {
    xs: 'w-3 h-3',
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-8 h-8',
    xl: 'w-12 h-12'
  };

  const colors = {
    primary: 'text-blue-600',
    secondary: 'text-gray-600',
    success: 'text-green-600',
    warning: 'text-yellow-600',
    danger: 'text-red-600',
    white: 'text-white'
  };

  return (
    <div
      ref={ref}
      className={cn(
        'animate-spin rounded-full border-2 border-current border-t-transparent',
        sizes[size],
        colors[color],
        className
      )}
      {...props}
    >
      <span className="sr-only">Загрузка...</span>
    </div>
  );
});

Spinner.displayName = 'Spinner';

// Дополнительные варианты спиннеров
const DotsSpinner = React.forwardRef(({ 
  size = 'md',
  color = 'primary',
  className = '',
  ...props 
}, ref) => {
  const sizes = {
    xs: 'w-1 h-1',
    sm: 'w-1.5 h-1.5',
    md: 'w-2 h-2',
    lg: 'w-3 h-3',
    xl: 'w-4 h-4'
  };

  const colors = {
    primary: 'bg-blue-600',
    secondary: 'bg-gray-600',
    success: 'bg-green-600',
    warning: 'bg-yellow-600',
    danger: 'bg-red-600',
    white: 'bg-white'
  };

  return (
    <div
      ref={ref}
      className={cn('flex space-x-1', className)}
      {...props}
    >
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className={cn(
            'rounded-full animate-pulse',
            sizes[size],
            colors[color]
          )}
          style={{
            animationDelay: `${i * 0.2}s`,
            animationDuration: '1s'
          }}
        />
      ))}
      <span className="sr-only">Загрузка...</span>
    </div>
  );
});

DotsSpinner.displayName = 'DotsSpinner';

const PulseSpinner = React.forwardRef(({ 
  size = 'md',
  color = 'primary',
  className = '',
  ...props 
}, ref) => {
  const sizes = {
    xs: 'w-3 h-3',
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-8 h-8',
    xl: 'w-12 h-12'
  };

  const colors = {
    primary: 'bg-blue-600',
    secondary: 'bg-gray-600',
    success: 'bg-green-600',
    warning: 'bg-yellow-600',
    danger: 'bg-red-600',
    white: 'bg-white'
  };

  return (
    <div
      ref={ref}
      className={cn(
        'rounded-full animate-ping',
        sizes[size],
        colors[color],
        className
      )}
      {...props}
    >
      <span className="sr-only">Загрузка...</span>
    </div>
  );
});

PulseSpinner.displayName = 'PulseSpinner';

export default Spinner;
export { DotsSpinner, PulseSpinner };



