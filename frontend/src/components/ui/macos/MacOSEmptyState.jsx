import React from 'react';

const MacOSEmptyState = ({
  icon: Icon,
  title = 'Нет данных',
  description,
  action,
  size = 'md',
  variant = 'default',
  className,
  style
}) => {
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

  const containerStyle = {
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

  const iconStyle = {
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
    <div className={className} style={containerStyle}>
      {Icon && <Icon style={iconStyle} />}
      
      <h3 style={titleStyle}>{title}</h3>
      
      {description && (
        <p style={descriptionStyle}>{description}</p>
      )}
      
      {action && (
        <div style={actionStyle}>
          {action}
        </div>
      )}
    </div>
  );
};

export default MacOSEmptyState;
