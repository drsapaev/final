import React from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import './ModernContainer.css';

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
  const { theme, getColor } = useTheme();

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
      {...props}
    >
      {children}
    </div>
  );
};

export default ModernContainer;


