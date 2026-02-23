import { forwardRef } from 'react';
import PropTypes from 'prop-types';
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
  const handleKeyDown = (event) => {
    if (onClick && (event.key === 'Enter' || event.key === ' ')) {
      event.preventDefault();
      onClick(event);
    }
  };

  if (onClick) {
    return (
      <div
        ref={ref}
        className={`design-system-card ${className}`}
        style={finalStyles}
        onClick={onClick}
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
      ref={ref}
      className={`design-system-card ${className}`}
      style={finalStyles}
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
    borderBottom: `1px solid ${colors.semantic.border.medium}`,
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
    borderTop: `1px solid ${colors.semantic.border.medium}`,
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

Card.propTypes = {
  children: PropTypes.node,
  variant: PropTypes.string,
  hover: PropTypes.bool,
  className: PropTypes.string,
  style: PropTypes.object,
  onClick: PropTypes.func
};

CardHeader.propTypes = {
  children: PropTypes.node,
  className: PropTypes.string,
  style: PropTypes.object
};

CardContent.propTypes = {
  children: PropTypes.node,
  className: PropTypes.string,
  style: PropTypes.object
};

CardFooter.propTypes = {
  children: PropTypes.node,
  className: PropTypes.string,
  style: PropTypes.object
};

// Прикрепляем подкомпоненты к Card
Card.Header = CardHeader;
Card.Content = CardContent;
Card.Footer = CardFooter;

export default Card;
