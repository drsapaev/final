import React, { useId, type ReactNode, type CSSProperties } from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from '../../../i18n/useTranslation';

interface MacOSEmptyStateProps {
  icon?: React.ComponentType<any> | ReactNode;
  title?: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  size?: 'sm' | 'md' | 'lg' | string;
  variant?: string;
  className?: string;
  style?: CSSProperties;
  [key: string]: any;
}

const MacOSEmptyState = ({
  icon: Icon,
  title = 'Нет данных',
  description,
  action,
  size = 'md',
  variant = 'default',
  className,
  style
}: MacOSEmptyStateProps) => {
  const descriptionId = useId();
  const hasDescription = Boolean(description);

  const sizeStyles = {
    sm: {
      padding: '24px',
      iconSize: 32,
      titleFontSize: 'var(--mac-font-size-base)',
      descriptionFontSize: 'var(--mac-font-size-sm)',
      gap: '12px'
    },
    md: {
      padding: '32px',
      iconSize: 48,
      titleFontSize: 'var(--mac-font-size-lg)',
      descriptionFontSize: 'var(--mac-font-size-base)',
      gap: '16px'
    },
    lg: {
      padding: '48px',
      iconSize: 64,
      titleFontSize: 'var(--mac-font-size-xl)',
      descriptionFontSize: 'var(--mac-font-size-lg)',
      gap: '20px'
    }
  };

  const variantStyles = {
    default: {
      background: 'var(--mac-bg-primary)',
      border: '1px solid var(--mac-border)',
      borderRadius: 'var(--mac-radius-lg)'
    },
    filled: {
      background: 'var(--mac-bg-secondary)',
      border: 'none',
      borderRadius: 'var(--mac-radius-lg)'
    },
    minimal: {
      background: 'transparent',
      border: 'none',
      borderRadius: '0'
    }
  };

  const currentSize = sizeStyles[size];
  const currentVariant = variantStyles[variant];

  const containerStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    textAlign: 'center',
    padding: currentSize.padding,
    background: currentVariant.background,
    border: currentVariant.border,
    borderRadius: currentVariant.borderRadius,
    gap: currentSize.gap,
    ...style
  };

  const iconStyle: CSSProperties = {
    width: currentSize.iconSize,
    height: currentSize.iconSize,
    color: 'var(--mac-text-tertiary)',
    opacity: 0.6
  };

  const titleStyle = {
    fontSize: currentSize.titleFontSize,
    fontWeight: 'var(--mac-font-weight-semibold)',
    color: 'var(--mac-text-primary)',
    margin: 0,
    lineHeight: 1.3
  };

  const descriptionStyle = {
    fontSize: currentSize.descriptionFontSize,
    color: 'var(--mac-text-secondary)',
    margin: 0,
    lineHeight: 1.5,
    maxWidth: '400px'
  };

  const actionStyle = {
    marginTop: '8px'
  };

  return (
    <div
      className={className}
      role="status"
      aria-live="polite"
      aria-atomic="true"
      aria-describedby={hasDescription ? descriptionId : undefined}
      style={containerStyle}
    >
      {Icon && typeof Icon === 'function' && <Icon aria-hidden="true" focusable="false" style={iconStyle} />}
      {Icon && typeof Icon !== 'function' && <span aria-hidden="true">{Icon}</span>}

      <h3 style={titleStyle}>{title}</h3>

      {hasDescription && (
        <p id={descriptionId} style={descriptionStyle}>{description}</p>
      )}
      
      {action && (
        <div style={actionStyle}>
          {action}
        </div>
      )}
    </div>
  );
};


MacOSEmptyState.propTypes = {
  ...(MacOSEmptyState.propTypes || {}),
  action: PropTypes.any,
  className: PropTypes.any,
  description: PropTypes.any,
  icon: PropTypes.any,
  size: PropTypes.any,
  style: PropTypes.any,
  title: PropTypes.any,
  variant: PropTypes.any,
};

export default MacOSEmptyState;
