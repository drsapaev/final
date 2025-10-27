import React from 'react';
import { useTheme } from '../../../contexts/ThemeContext';

/**
 * macOS-style Card Component
 * Implements Apple's Human Interface Guidelines for cards and containers
 */
const Card = React.forwardRef(({
  children,
  variant = 'default',
  padding = 'default',
  shadow = 'default',
  interactive = false,
  onClick,
  className = '',
  style = {},
  ...props
}, ref) => {
  const { theme } = useTheme();

  // macOS card styles based on variant
  const getCardStyles = () => {
    const baseStyles = {
      backgroundColor: 'var(--mac-bg-primary)',
      border: '1px solid var(--mac-border)',
      borderRadius: 'var(--mac-radius-lg)', // Стандартный радиус macOS для карточек
      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
      position: 'relative',
      overflow: 'hidden',
      transition: 'all var(--mac-duration-normal) var(--mac-ease)',
      backdropFilter: 'var(--mac-blur-light)',
      WebkitBackdropFilter: 'var(--mac-blur-light)'
    };

    const paddingStyles = {
      none: { padding: '0' },
      small: { padding: '12px' },
      default: { padding: '20px' },
      large: { padding: '32px' }
    };

    const shadowStyles = {
      none: { boxShadow: 'none' },
      small: { boxShadow: 'var(--mac-shadow-sm)' },
      default: { boxShadow: 'var(--mac-shadow-md)' },
      large: { boxShadow: 'var(--mac-shadow-lg)' }
    };

    const variantStyles = {
      default: {},
      elevated: {
        boxShadow: 'var(--mac-shadow-lg)',
        border: '1px solid var(--mac-border-secondary)'
      },
      outlined: {
        backgroundColor: 'transparent',
        border: '2px solid var(--mac-border)'
      },
      filled: {
        backgroundColor: 'var(--mac-bg-tertiary)',
        border: '1px solid var(--mac-border-secondary)'
      }
    };

    return {
      ...baseStyles,
      ...paddingStyles[padding],
      ...shadowStyles[shadow],
      ...variantStyles[variant],
      ...(interactive && {
        cursor: 'pointer',
        ':hover': {
          transform: 'translateY(-2px)',
          boxShadow: '0 8px 20px rgba(0, 0, 0, 0.12)'
        },
        ':active': {
          transform: 'translateY(0)'
        }
      }),
      ...style
    };
  };

  const handleClick = (e) => {
    if (interactive && onClick) {
      onClick(e);
    }
  };

  const cardStyles = getCardStyles();

  return (
    <div
      ref={ref}
      className={`mac-card ${interactive ? 'mac-card--interactive' : ''} ${className}`}
      style={cardStyles}
      onClick={handleClick}
      {...props}
    >
      {/* Card content */}
      {children}

      {/* Interactive overlay effect */}
      {interactive && (
        <div
          className="mac-card-overlay"
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 122, 255, 0.02)',
            opacity: 0,
            transition: 'opacity 0.2s cubic-bezier(0.2, 0.8, 0.2, 1)',
            pointerEvents: 'none',
            borderRadius: 'inherit'
          }}
        />
      )}

      <style>{`
        .mac-card:hover .mac-card-overlay {
          opacity: 1 !important;
        }

        /* Dark mode adjustments */
        @media (prefers-color-scheme: dark) {
          .mac-card {
            background-color: rgba(255, 255, 255, 0.05) !important;
            border-color: rgba(255, 255, 255, 0.1) !important;
            color: #f5f5f7 !important;
          }

          .mac-card--interactive:hover {
            background-color: rgba(255, 255, 255, 0.08) !important;
            border-color: rgba(255, 255, 255, 0.15) !important;
          }
        }

        /* High contrast mode */
        @media (prefers-contrast: high) {
          .mac-card {
            border-width: 2px !important;
          }
        }

        /* Reduced motion */
        @media (prefers-reduced-motion: reduce) {
          .mac-card,
          .mac-card-overlay {
            transition: none !important;
          }

          .mac-card--interactive:hover {
            transform: none !important;
          }
        }

        /* Touch device optimizations */
        @media (hover: none) and (pointer: coarse) {
          .mac-card--interactive:active {
            transform: scale(0.98) !important;
          }
        }
      `}</style>
    </div>
  );
});

Card.displayName = 'macOS Card';

/**
 * macOS-style Card Header Component
 */
export const CardHeader = React.forwardRef(({
  children,
  className = '',
  style = {},
  ...props
}, ref) => {
  return (
    <div
      ref={ref}
      className={`mac-card-header ${className}`}
      style={{
        marginBottom: '16px',
        paddingBottom: '12px',
        borderBottom: '1px solid rgba(0, 0, 0, 0.1)',
        ...style
      }}
      {...props}
    >
      {children}
    </div>
  );
});

CardHeader.displayName = 'macOS Card Header';

/**
 * macOS-style Card Title Component
 */
export const CardTitle = React.forwardRef(({
  children,
  className = '',
  style = {},
  ...props
}, ref) => {
  return (
    <h3
      ref={ref}
      className={`mac-card-title ${className}`}
      style={{
        fontSize: '17px',
        fontWeight: '600',
        color: 'var(--mac-text-primary)',
        margin: '0 0 4px 0',
        fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
        borderRadius: 'var(--mac-radius-sm)',
        ...style
      }}
      {...props}
    >
      {children}
    </h3>
  );
});

CardTitle.displayName = 'macOS Card Title';

/**
 * macOS-style Card Description Component
 */
export const CardDescription = React.forwardRef(({
  children,
  className = '',
  style = {},
  ...props
}, ref) => {
  return (
    <p
      ref={ref}
      className={`mac-card-description ${className}`}
      style={{
        fontSize: '13px',
        color: 'var(--mac-text-secondary)',
        margin: '0',
        lineHeight: '1.4',
        fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
        ...style
      }}
      {...props}
    >
      {children}
    </p>
  );
});

CardDescription.displayName = 'macOS Card Description';

/**
 * macOS-style Card Content Component
 */
export const CardContent = React.forwardRef(({
  children,
  className = '',
  style = {},
  ...props
}, ref) => {
  return (
    <div
      ref={ref}
      className={`mac-card-content ${className}`}
      style={{
        color: 'var(--mac-text-primary)',
        fontSize: '13px',
        lineHeight: '1.5',
        fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
        ...style
      }}
      {...props}
    >
      {children}
    </div>
  );
});

CardContent.displayName = 'macOS Card Content';

/**
 * macOS-style Card Footer Component
 */
export const CardFooter = React.forwardRef(({
  children,
  className = '',
  style = {},
  ...props
}, ref) => {
  return (
    <div
      ref={ref}
      className={`mac-card-footer ${className}`}
      style={{
        marginTop: '16px',
        paddingTop: '12px',
        borderTop: '1px solid rgba(0, 0, 0, 0.1)',
        display: 'flex',
        justifyContent: 'flex-end',
        gap: '8px',
        ...style
      }}
      {...props}
    >
      {children}
    </div>
  );
});

CardFooter.displayName = 'macOS Card Footer';

export default Card;

