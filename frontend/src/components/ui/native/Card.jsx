import React from 'react';
import { useTheme } from '../../../contexts/ThemeContext';

const Card = React.forwardRef(({
  children,
  className = '',
  variant = 'default',
  padding = 'md',
  shadow = 'md',
  style = {},
  ...props
}, ref) => {
  const { isDark, getColor, getSpacing, getShadow } = useTheme();

  const baseStyle = {
    borderRadius: '8px',
    backgroundColor: getColor('surface'),
    border: `1px solid ${getColor('border')}`,
    color: getColor('text')
  };

  const variants = {
    default: {},
    elevated: {
      boxShadow: getShadow('lg')
    },
    outlined: {
      border: `2px solid ${getColor('border')}`
    },
    ghost: {
      backgroundColor: 'transparent',
      border: '1px solid transparent'
    },
    primary: {
      backgroundColor: getColor('primary', 50),
      border: `1px solid ${getColor('primary', 200)}`
    },
    success: {
      backgroundColor: getColor('success', 50),
      border: `1px solid ${getColor('success', 200)}`
    },
    warning: {
      backgroundColor: getColor('warning', 50),
      border: `1px solid ${getColor('warning', 200)}`
    },
    danger: {
      backgroundColor: getColor('danger', 50),
      border: `1px solid ${getColor('danger', 200)}`
    }
  };

  const paddings = {
    none: { padding: 0 },
    sm: { padding: getSpacing('md') },
    md: { padding: getSpacing('lg') },
    lg: { padding: getSpacing('xl') },
    xl: { padding: getSpacing('xl') }
  };

  const shadows = {
    none: { boxShadow: 'none' },
    sm: { boxShadow: getShadow('sm') },
    md: { boxShadow: getShadow('md') },
    lg: { boxShadow: getShadow('lg') },
    xl: { boxShadow: getShadow('xl') }
  };

  const combinedStyle = {
    ...baseStyle,
    ...variants[variant],
    ...paddings[padding],
    ...shadows[shadow],
    ...style
  };

  return (
    <div
      ref={ref}
      className={className}
      style={combinedStyle}
      {...props}
    >
      {children}
    </div>
  );
});

Card.displayName = 'Card';

const CardHeader = React.forwardRef(({
  children,
  className = '',
  style = {},
  ...props
}, ref) => {
  const { getSpacing } = useTheme();

  return (
    <div
      ref={ref}
      className={className}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: getSpacing('xs'),
        padding: getSpacing('xl'),
        ...style
      }}
      {...props}
    >
      {children}
    </div>
  );
});

CardHeader.displayName = 'CardHeader';

const CardTitle = React.forwardRef(({
  children,
  className = '',
  style = {},
  ...props
}, ref) => {
  const { getFontSize, getColor } = useTheme();

  return (
    <h3
      ref={ref}
      className={className}
      style={{
        fontSize: getFontSize('xl'),
        fontWeight: '600',
        lineHeight: '1.2',
        letterSpacing: '-0.025em',
        color: getColor('text'),
        ...style
      }}
      {...props}
    >
      {children}
    </h3>
  );
});

CardTitle.displayName = 'CardTitle';

const CardDescription = React.forwardRef(({
  children,
  className = '',
  style = {},
  ...props
}, ref) => {
  const { getFontSize, getColor } = useTheme();

  return (
    <p
      ref={ref}
      className={className}
      style={{
        fontSize: getFontSize('sm'),
        color: getColor('textSecondary'),
        ...style
      }}
      {...props}
    >
      {children}
    </p>
  );
});

CardDescription.displayName = 'CardDescription';

const CardContent = React.forwardRef(({
  children,
  className = '',
  style = {},
  ...props
}, ref) => {
  const { getSpacing } = useTheme();

  return (
    <div
      ref={ref}
      className={className}
      style={{
        padding: getSpacing('xl'),
        paddingTop: 0,
        ...style
      }}
      {...props}
    >
      {children}
    </div>
  );
});

CardContent.displayName = 'CardContent';

const CardFooter = React.forwardRef(({
  children,
  className = '',
  style = {},
  ...props
}, ref) => {
  const { getSpacing } = useTheme();

  return (
    <div
      ref={ref}
      className={className}
      style={{
        display: 'flex',
        alignItems: 'center',
        padding: getSpacing('xl'),
        paddingTop: 0,
        ...style
      }}
      {...props}
    >
      {children}
    </div>
  );
});

CardFooter.displayName = 'CardFooter';

// Прикрепляем подкомпоненты к основному компоненту Card (после их объявления)
Card.Header = CardHeader;
Card.Title = CardTitle;
Card.Description = CardDescription;
Card.Content = CardContent;
Card.Footer = CardFooter;

export default Card;
export { CardHeader, CardTitle, CardDescription, CardContent, CardFooter };



