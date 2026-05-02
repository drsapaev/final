import { forwardRef } from 'react';
import { createBadgeStyles } from './utils';
import { SIZES } from './types';
import PropTypes from 'prop-types';

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
      {...props}>
      
      {children}
    </span>);

});


Badge.propTypes = {
  ...(Badge.propTypes || {}),
  children: PropTypes.any,
  className: PropTypes.any,
  size: PropTypes.any,
  style: PropTypes.any,
  variant: PropTypes.any,
};

Badge.displayName = 'Badge';

export default Badge;