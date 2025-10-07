import React from 'react';
import { cn } from '../../../utils/cn';

const Card = React.forwardRef(({ 
  children, 
  className = '', 
  variant = 'default',
  padding = 'md',
  shadow = 'md',
  ...props 
}, ref) => {
  const baseClasses = 'rounded-lg border bg-card text-card-foreground';
  
  const variants = {
    default: 'bg-white border-gray-200',
    elevated: 'bg-white border-gray-200 shadow-lg',
    outlined: 'bg-white border-2 border-gray-300',
    ghost: 'bg-transparent border-transparent',
    primary: 'bg-blue-50 border-blue-200',
    success: 'bg-green-50 border-green-200',
    warning: 'bg-yellow-50 border-yellow-200',
    danger: 'bg-red-50 border-red-200'
  };
  
  const paddings = {
    none: '',
    sm: 'p-3',
    md: 'p-4',
    lg: 'p-6',
    xl: 'p-8'
  };
  
  const shadows = {
    none: '',
    sm: 'shadow-sm',
    md: 'shadow-md',
    lg: 'shadow-lg',
    xl: 'shadow-xl'
  };
  
  return (
    <div
      ref={ref}
      className={cn(
        baseClasses,
        variants[variant],
        paddings[padding],
        shadows[shadow],
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
});

Card.displayName = 'Card';

const CardHeader = React.forwardRef(({
  children,
  className = '',
  ...props
}, ref) => (
  <div
    ref={ref}
    className={cn('flex flex-col space-y-1.5 p-6', className)}
    {...props}
  >
    {children}
  </div>
));

CardHeader.displayName = 'CardHeader';

const CardTitle = React.forwardRef(({
  children,
  className = '',
  ...props
}, ref) => (
  <h3
    ref={ref}
    className={cn('text-2xl font-semibold leading-none tracking-tight', className)}
    {...props}
  >
    {children}
  </h3>
));

CardTitle.displayName = 'CardTitle';

const CardDescription = React.forwardRef(({
  children,
  className = '',
  ...props
}, ref) => (
  <p
    ref={ref}
    className={cn('text-sm text-muted-foreground', className)}
    {...props}
  >
    {children}
  </p>
));

CardDescription.displayName = 'CardDescription';

const CardContent = React.forwardRef(({
  children,
  className = '',
  ...props
}, ref) => (
  <div
    ref={ref}
    className={cn('p-6 pt-0', className)}
    {...props}
  >
    {children}
  </div>
));

CardContent.displayName = 'CardContent';

const CardFooter = React.forwardRef(({
  children,
  className = '',
  ...props
}, ref) => (
  <div
    ref={ref}
    className={cn('flex items-center p-6 pt-0', className)}
    {...props}
  >
    {children}
  </div>
));

CardFooter.displayName = 'CardFooter';

// Прикрепляем подкомпоненты к основному компоненту Card (после их объявления)
Card.Header = CardHeader;
Card.Title = CardTitle;
Card.Description = CardDescription;
Card.Content = CardContent;
Card.Footer = CardFooter;

export default Card;
export { CardHeader, CardTitle, CardDescription, CardContent, CardFooter };



