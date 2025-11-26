import React from 'react';
import { cn } from '../../../utils/cn';

/**
 * Компонент для анимированных переходов
 */
const AnimatedTransition = ({ 
  children, 
  show = true, 
  type = 'fade',
  duration = 300,
  className = '',
  ...props 
}) => {
  const baseClasses = 'transition-all ease-in-out';
  
  const typeClasses = {
    fade: show ? 'opacity-100' : 'opacity-0',
    slide: show ? 'transform translate-x-0' : 'transform -translate-x-full',
    scale: show ? 'transform scale-100' : 'transform scale-95',
    slideUp: show ? 'transform translate-y-0' : 'transform translate-y-4'
  };

  const durationClasses = {
    150: 'duration-150',
    200: 'duration-200',
    300: 'duration-300',
    500: 'duration-500',
    700: 'duration-700'
  };

  const classes = cn(
    baseClasses,
    typeClasses[type] || typeClasses.fade,
    durationClasses[duration] || durationClasses[300],
    className
  );

  if (!show && type === 'fade') {
    return null;
  }

  return (
    <div className={classes} {...props}>
      {children}
    </div>
  );
};

export default AnimatedTransition;


