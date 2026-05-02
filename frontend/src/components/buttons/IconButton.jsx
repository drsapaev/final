import ModernButton from './ModernButton';
import './IconButton.css';
import PropTypes from 'prop-types';

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


IconButton.propTypes = {
  ...(IconButton.propTypes || {}),
  className: PropTypes.any,
  icon: PropTypes.any,
  rounded: PropTypes.any,
  size: PropTypes.any,
  tooltip: PropTypes.any,
  variant: PropTypes.any,
};

export default IconButton;


