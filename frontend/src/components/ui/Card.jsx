import React from 'react';
import { useTheme } from '../../contexts/ThemeContext';

const Card = ({
  children,
  variant = 'default',
  padding = 'md',
  className = '',
  style = {},
  ...props
}) => {
  const { isDark, isLight, getColor, getSpacing, getShadow } = useTheme();

  // Варианты карточек с использованием централизованной темы
  const variants = {
    default: {
      background: isLight ? 'rgba(255, 255, 255, 0.8)' : 'rgba(30, 41, 59, 0.8)',
      border: `1px solid ${isLight ? 'rgba(255, 255, 255, 0.2)' : 'rgba(255, 255, 255, 0.1)'}`,
      boxShadow: getShadow('xl')
    },
    elevated: {
      background: isLight ? 'rgba(255, 255, 255, 0.9)' : 'rgba(30, 41, 59, 0.9)',
      border: `1px solid ${isLight ? 'rgba(255, 255, 255, 0.3)' : 'rgba(255, 255, 255, 0.2)'}`,
      boxShadow: getShadow('2xl')
    },
    glass: {
      background: 'rgba(255, 255, 255, 0.1)',
      border: '1px solid rgba(255, 255, 255, 0.2)',
      backdropFilter: 'blur(20px)',
      boxShadow: '0 8px 32px 0 rgba(31, 38, 135, 0.37)'
    }
  };

  // Размеры отступов используя централизованную систему
  const paddings = {
    none: '0',
    xs: getSpacing('xs'),
    sm: getSpacing('sm'),
    md: getSpacing('md'),
    lg: getSpacing('lg'),
    xl: getSpacing('xl')
  };

  // Базовые стили
  const baseStyles = {
    borderRadius: '20px',
    overflow: 'hidden',
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    position: 'relative',
    ...variants[variant],
    padding: paddings[padding]
  };

  return (
    <div
      style={{
        ...baseStyles,
        ...style
      }}
      className={className}
      {...props}
    >
      {children}
    </div>
  );
};

// Компонент для заголовка карточки
const CardHeader = ({ children, className = '', style = {}, ...props }) => {
  const headerStyles = {
    padding: '32px',
    borderBottom: '1px solid rgba(255, 255, 255, 0.2)',
    background: 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 50%, #1e3a8a 100%)',
    color: 'white',
    position: 'relative',
    overflow: 'hidden',
    ...style
  };

  return (
    <div
      style={headerStyles}
      className={className}
      {...props}
    >
      {children}
    </div>
  );
};

// Компонент для содержимого карточки
const CardContent = ({ children, className = '', style = {}, ...props }) => {
  const contentStyles = {
    padding: '24px',
    ...style
  };

  return (
    <div
      style={contentStyles}
      className={className}
      {...props}
    >
      {children}
    </div>
  );
};

// Компонент для футера карточки
const CardFooter = ({ children, className = '', style = {}, ...props }) => {
  const footerStyles = {
    padding: '16px 24px',
    borderTop: '1px solid rgba(255, 255, 255, 0.1)',
    background: 'rgba(255, 255, 255, 0.05)',
    ...style
  };

  return (
    <div
      style={footerStyles}
      className={className}
      {...props}
    >
      {children}
    </div>
  );
};

// Экспортируем все компоненты
Card.Header = CardHeader;
Card.Content = CardContent;
Card.Footer = CardFooter;

export default Card;
