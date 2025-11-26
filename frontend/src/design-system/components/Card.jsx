import React, { forwardRef } from 'react';
import { createCardStyles } from './utils';
import { colors } from '../../theme/tokens';

const Card = forwardRef(({
  children,
  variant = 'default',
  hover = true,
  className = '',
  style = {},
  onClick,
  ...props
}, ref) => {
  const cardStyles = createCardStyles(variant, hover);
  
  const finalStyles = {
    ...cardStyles,
    ...style
  };

  return (
    <div
      ref={ref}
      className={`design-system-card ${className}`}
      style={finalStyles}
      onClick={onClick}
      {...props}
    >
      {children}
    </div>
  );
});

Card.displayName = 'Card';

// Подкомпоненты Card
const CardHeader = forwardRef(({
  children,
  className = '',
  style = {},
  ...props
}, ref) => {
  const headerStyles = {
    padding: '24px 24px 0 24px',
    borderBottom: `1px solid ${colors.border.medium}`,
    marginBottom: '16px',
    ...style
  };

  return (
    <div
      ref={ref}
      className={`design-system-card-header ${className}`}
      style={headerStyles}
      {...props}
    >
      {children}
    </div>
  );
});

CardHeader.displayName = 'CardHeader';

const CardContent = forwardRef(({
  children,
  className = '',
  style = {},
  ...props
}, ref) => {
  const contentStyles = {
    padding: '0 24px',
    ...style
  };

  return (
    <div
      ref={ref}
      className={`design-system-card-content ${className}`}
      style={contentStyles}
      {...props}
    >
      {children}
    </div>
  );
});

CardContent.displayName = 'CardContent';

const CardFooter = forwardRef(({
  children,
  className = '',
  style = {},
  ...props
}, ref) => {
  const footerStyles = {
    padding: '16px 24px 24px 24px',
    borderTop: `1px solid ${colors.border.medium}`,
    marginTop: '16px',
    ...style
  };

  return (
    <div
      ref={ref}
      className={`design-system-card-footer ${className}`}
      style={footerStyles}
      {...props}
    >
      {children}
    </div>
  );
});

CardFooter.displayName = 'CardFooter';

// Прикрепляем подкомпоненты к Card
Card.Header = CardHeader;
Card.Content = CardContent;
Card.Footer = CardFooter;

export default Card;
