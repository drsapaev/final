import { useTheme } from '../../contexts/ThemeContext';
import './ModernContainer.css';
import PropTypes from 'prop-types';

const ModernContainer = ({
  children,
  maxWidth = 'xl',
  padding = 'medium',
  margin = 'auto',
  fluid = false,
  centered = false,
  className = '',
  ...props
}) => {
  useTheme();

  const maxWidthValues = {
    xs: '480px',
    sm: '640px',
    md: '768px',
    lg: '1024px',
    xl: '1280px',
    '2xl': '1536px',
    full: '100%'
  };

  const paddingValues = {
    none: '0',
    small: '12px',
    medium: '20px',
    large: '32px',
    xl: '48px'
  };

  const containerStyles = {
    maxWidth: fluid ? '100%' : maxWidthValues[maxWidth] || maxWidthValues.xl,
    padding: paddingValues[padding] || paddingValues.medium,
    margin: margin === 'auto' ? '0 auto' : margin,
    ...(centered && {
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center'
    })
  };

  return (
    <div
      className={`modern-container ${fluid ? 'fluid' : ''} ${centered ? 'centered' : ''} ${className}`}
      style={containerStyles}
      {...props}>
      
      {children}
    </div>);

};


ModernContainer.propTypes = {
  ...(ModernContainer.propTypes || {}),
  centered: PropTypes.any,
  children: PropTypes.any,
  className: PropTypes.any,
  fluid: PropTypes.any,
  margin: PropTypes.any,
  maxWidth: PropTypes.any,
  padding: PropTypes.any,
};

export default ModernContainer;