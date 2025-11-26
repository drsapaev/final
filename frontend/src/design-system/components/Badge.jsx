import React, { forwardRef } from 'react';
import { createBadgeStyles } from './utils';
import { SIZES, VARIANTS } from './types';

const Badge = forwardRef(({
  children,
  variant = 'default',
  size = SIZES.MD,
  className = '',
  style = {},
  ...props
}, ref) => {
  const badgeStyles = createBadgeStyles(variant, size);
  
  const finalStyles = {
    ...badgeStyles,
    ...style
  };

  return (
    <span
      ref={ref}
      className={`design-system-badge ${className}`}
      style={finalStyles}
      {...props}
    >
      {children}
    </span>
  );
});

Badge.displayName = 'Badge';

export default Badge;
