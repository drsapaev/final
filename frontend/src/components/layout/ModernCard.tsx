import React from 'react';

import { useTheme } from '../../contexts/ThemeContext';
import './ModernCard.css';
import { useTranslation } from '../../i18n/useTranslation';

interface ModernCardProps {
  children?: React.ReactNode;
  variant?: string;
  padding?: 'none' | 'small' | 'medium' | 'large' | 'xl';
  shadow?: 'none' | 'small' | 'medium' | 'large' | 'xl';
  border?: boolean;
  rounded?: boolean;
  hoverable?: boolean;
  clickable?: boolean;
  onClick?: (e: React.MouseEvent<HTMLDivElement> | React.KeyboardEvent<HTMLDivElement>) => void;
  className?: string;
  [key: string]: unknown;
}

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
}: ModernCardProps) => {
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
    padding: paddingValues[padding as keyof typeof paddingValues] || paddingValues.medium,
    boxShadow: theme === 'dark' 
      ? shadowValues[shadow as keyof typeof shadowValues]?.replace('rgba(0, 0, 0,', 'rgba(0, 0, 0,') 
      : shadowValues[shadow as keyof typeof shadowValues] || shadowValues.medium,
    cursor: clickable ? 'pointer' : 'default'
  };

  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (clickable && onClick) {
      onClick(e);
    }
  };
  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (clickable && onClick && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault();
      onClick(e);
    }
  };
  const cardClassName = `modern-card variant-${variant} ${hoverable ? 'hoverable' : ''} ${clickable ? 'clickable' : ''} ${rounded ? 'rounded' : ''} ${className}`;

  if (clickable && onClick) {
    return (
      <div
        className={cardClassName}
        style={cardStyles}
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        role="button"
        tabIndex={0}
        {...props}
      >
        {children}
      </div>
    );
  }

  return (
    <div
      className={cardClassName}
      style={cardStyles}
      {...props}
    >
      {children}
    </div>
  );
};

// Компоненты частей карточки
interface CardPartProps {
  children?: React.ReactNode;
  className?: string;
  [key: string]: unknown;
}

export const CardHeader = ({ 
  children, 
  className = '',
  ...props 
}: CardPartProps) => (
  <div className={`card-header ${className}`} {...props}>
    {children}
  </div>
);

export const CardBody = ({ 
  children, 
  className = '',
  ...props 
}: CardPartProps) => (
  <div className={`card-body ${className}`} {...props}>
    {children}
  </div>
);

export const CardFooter = ({ 
  children, 
  className = '',
  ...props 
}: CardPartProps) => (
  <div className={`card-footer ${className}`} {...props}>
    {children}
  </div>
);

interface CardTitleProps extends CardPartProps {
  level?: number;
}

export const CardTitle = ({ 
  children, 
  level = 3,
  className = '',
  ...props 
}: CardTitleProps) => {
  const Tag = `h${level}` as unknown as React.ElementType;
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
}: CardPartProps) => (
  <p className={`card-description ${className}`} {...props}>
    {children}
  </p>
);







export default ModernCard;


