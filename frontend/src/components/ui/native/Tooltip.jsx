import React, { useState, useRef, useEffect } from 'react';
import { cn } from '../../../utils/cn';

// Простая нативная реализация тултипа без сторонних зависимостей
const Tooltip = React.forwardRef(({ 
  children,
  content,
  position = 'top',
  delay = 150,
  disabled = false,
  className = '',
  contentClassName = '',
  ...props
}, ref) => {
  const [visible, setVisible] = useState(false);
  const [timer, setTimer] = useState(null);
  const triggerRef = useRef(null);
  const tooltipRef = useRef(null);

  useEffect(() => () => { if (timer) clearTimeout(timer); }, [timer]);

  const show = () => {
    if (disabled) return;
    const t = setTimeout(() => setVisible(true), delay);
    setTimer(t);
  };

  const hide = () => {
    if (timer) clearTimeout(timer);
    setVisible(false);
  };

  const positions = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
    left: 'right-full top-1/2 -translate-y-1/2 mr-2',
    right: 'left-full top-1/2 -translate-y-1/2 ml-2'
  };

  return (
    <span
      ref={ref}
      className={cn('relative inline-flex', className)}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
      {...props}
    >
      <span ref={triggerRef} className="inline-flex">
        {children}
      </span>

      {visible && content && (
        <span
          ref={tooltipRef}
          role="tooltip"
          className={cn(
            'absolute z-50 px-2 py-1 text-xs text-white bg-gray-900 rounded shadow-md',
            'animate-in fade-in-0 zoom-in-95 duration-150 whitespace-nowrap',
            positions[position] || positions.top,
            contentClassName
          )}
        >
          {content}
          <span
            className={cn(
              'absolute w-2 h-2 bg-gray-900 rotate-45',
              position === 'top' && 'top-full left-1/2 -translate-x-1/2',
              position === 'bottom' && 'bottom-full left-1/2 -translate-x-1/2',
              position === 'left' && 'left-full top-1/2 -translate-y-1/2',
              position === 'right' && 'right-full top-1/2 -translate-y-1/2'
            )}
          />
        </span>
      )}
    </span>
  );
});

Tooltip.displayName = 'Tooltip';

export default Tooltip;


