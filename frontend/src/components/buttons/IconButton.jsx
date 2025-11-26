import React from 'react';
import ModernButton from './ModernButton';
import './IconButton.css';

const IconButton = ({
  icon,
  size = 'medium',
  variant = 'ghost',
  rounded = true,
  tooltip,
  className = '',
  ...props
}) => {
  return (
    <ModernButton
      icon={icon}
      size={size}
      variant={variant}
      rounded={rounded}
      className={`icon-button ${className}`}
      title={tooltip}
      aria-label={tooltip}
      {...props}
    />
  );
};

export default IconButton;


