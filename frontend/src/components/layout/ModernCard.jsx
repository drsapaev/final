import React from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import './ModernCard.css';

const ModernCard = ({
  children,
  variant = 'default',
  padding = 'medium',
  shadow = 'medium',
  border = true,
  rounded = true,
  hoverable = false,
  clickable = false,
  onClick,
  className = '',
  ...props
}) => {
  const { theme, getColor } = useTheme();

  const paddingValues = {
    none: '0',
    small: '12px',
    medium: '20px',
    large: '32px',
    xl: '48px'
  };

  const shadowValues = {
    none: 'none',
    small: '0 1px 3px rgba(0, 0, 0, 0.1)',
    medium: '0 4px 6px rgba(0, 0, 0, 0.1)',
    large: '0 10px 15px rgba(0, 0, 0, 0.1)',
    xl: '0 20px 25px rgba(0, 0, 0, 0.1)'
  };

  const cardStyles = {
    backgroundColor: getColor('cardBg'),
    color: getColor('textPrimary'),
    borderColor: border ? getColor('border') : 'transparent',
    padding: paddingValues[padding] || paddingValues.medium,
    boxShadow: theme === 'dark' 
      ? shadowValues[shadow]?.replace('rgba(0, 0, 0,', 'rgba(0, 0, 0,') 
      : shadowValues[shadow] || shadowValues.medium,
    cursor: clickable ? 'pointer' : 'default'
  };

  const handleClick = (e) => {
    if (clickable && onClick) {
      onClick(e);
    }
  };

  return (
    <div
      className={`modern-card variant-${variant} ${hoverable ? 'hoverable' : ''} ${clickable ? 'clickable' : ''} ${rounded ? 'rounded' : ''} ${className}`}
      style={cardStyles}
      onClick={handleClick}
      role={clickable ? 'button' : undefined}
      tabIndex={clickable ? 0 : undefined}
      {...props}
    >
      {children}
    </div>
  );
};

// Компоненты частей карточки
export const CardHeader = ({ 
  children, 
  className = '',
  ...props 
}) => (
  <div className={`card-header ${className}`} {...props}>
    {children}
  </div>
);

export const CardBody = ({ 
  children, 
  className = '',
  ...props 
}) => (
  <div className={`card-body ${className}`} {...props}>
    {children}
  </div>
);

export const CardFooter = ({ 
  children, 
  className = '',
  ...props 
}) => (
  <div className={`card-footer ${className}`} {...props}>
    {children}
  </div>
);

export const CardTitle = ({ 
  children, 
  level = 3,
  className = '',
  ...props 
}) => {
  const Tag = `h${level}`;
  return (
    <Tag className={`card-title ${className}`} {...props}>
      {children}
    </Tag>
  );
};

export const CardDescription = ({ 
  children, 
  className = '',
  ...props 
}) => (
  <p className={`card-description ${className}`} {...props}>
    {children}
  </p>
);

export default ModernCard;


