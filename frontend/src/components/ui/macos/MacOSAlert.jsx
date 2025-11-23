import React from 'react';
import { AlertCircle, CheckCircle, Info, AlertTriangle, X } from 'lucide-react';

const MacOSAlert = ({
  type = 'info',
  title,
  description,
  action,
  dismissible = false,
  onDismiss,
  size = 'md',
  variant = 'default',
  className,
  style
}) => {
  const sizeStyles = {
    sm: {
      padding: '12px 16px',
      fontSize: 'var(--mac-font-size-sm)',
      titleFontSize: 'var(--mac-font-size-sm)',
      iconSize: 16,
      gap: '8px'
    },
    md: {
      padding: '16px 20px',
      fontSize: 'var(--mac-font-size-base)',
      titleFontSize: 'var(--mac-font-size-base)',
      iconSize: 20,
      gap: '12px'
    },
    lg: {
      padding: '20px 24px',
      fontSize: 'var(--mac-font-size-lg)',
      titleFontSize: 'var(--mac-font-size-lg)',
      iconSize: 24,
      gap: '16px'
    }
  };

  const typeStyles = {
    info: {
      background: 'var(--mac-bg-blue)',
      border: '1px solid var(--mac-accent-blue)',
      icon: Info,
      iconColor: 'var(--mac-accent-blue)',
      textColor: 'var(--mac-accent-blue)'
    },
    success: {
      background: 'var(--mac-bg-success)',
      border: '1px solid var(--mac-success)',
      icon: CheckCircle,
      iconColor: 'var(--mac-success)',
      textColor: 'var(--mac-success)'
    },
    warning: {
      background: 'var(--mac-bg-warning)',
      border: '1px solid var(--mac-warning)',
      icon: AlertTriangle,
      iconColor: 'var(--mac-warning)',
      textColor: 'var(--mac-warning)'
    },
    error: {
      background: 'var(--mac-bg-error)',
      border: '1px solid var(--mac-error)',
      icon: AlertCircle,
      iconColor: 'var(--mac-error)',
      textColor: 'var(--mac-error)'
    }
  };

  const variantStyles = {
    default: {
      borderRadius: 'var(--mac-radius-md)'
    },
    filled: {
      borderRadius: 'var(--mac-radius-md)',
      border: 'none'
    },
    minimal: {
      borderRadius: 'var(--mac-radius-sm)',
      border: 'none',
      background: 'transparent'
    }
  };

  const currentSize = sizeStyles[size];
  const currentType = typeStyles[type];
  const currentVariant = variantStyles[variant];
  const IconComponent = currentType.icon;

  const alertStyle = {
    display: 'flex',
    alignItems: 'flex-start',
    padding: currentSize.padding,
    background: currentVariant.background || currentType.background,
    border: currentVariant.border || currentType.border,
    borderRadius: currentVariant.borderRadius,
    gap: currentSize.gap,
    position: 'relative',
    ...style
  };

  const iconStyle = {
    width: currentSize.iconSize,
    height: currentSize.iconSize,
    color: currentType.iconColor,
    flexShrink: 0,
    marginTop: '2px'
  };

  const contentStyle = {
    flex: 1,
    minWidth: 0
  };

  const titleStyle = {
    fontSize: currentSize.titleFontSize,
    fontWeight: 'var(--mac-font-weight-semibold)',
    color: currentType.textColor,
    margin: 0,
    marginBottom: description ? '4px' : 0,
    lineHeight: 1.3
  };

  const descriptionStyle = {
    fontSize: currentSize.fontSize,
    color: 'var(--mac-text-primary)',
    margin: 0,
    lineHeight: 1.5
  };

  const actionStyle = {
    marginTop: '12px'
  };

  const dismissButtonStyle = {
    position: 'absolute',
    top: '12px',
    right: '12px',
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    padding: '4px',
    borderRadius: 'var(--mac-radius-sm)',
    color: 'var(--mac-text-tertiary)',
    transition: 'all var(--mac-duration-normal) var(--mac-ease)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center'
  };

  const handleDismiss = () => {
    if (onDismiss) {
      onDismiss();
    }
  };

  const handleDismissMouseEnter = (e) => {
    e.target.style.background = 'var(--mac-bg-tertiary)';
    e.target.style.color = 'var(--mac-text-primary)';
  };

  const handleDismissMouseLeave = (e) => {
    e.target.style.background = 'none';
    e.target.style.color = 'var(--mac-text-tertiary)';
  };

  return (
    <div className={className} style={alertStyle} role="alert">
      <IconComponent style={iconStyle} />
      
      <div style={contentStyle}>
        {title && (
          <h4 style={titleStyle}>{title}</h4>
        )}
        
        {description && (
          <p style={descriptionStyle}>{description}</p>
        )}
        
        {action && (
          <div style={actionStyle}>
            {action}
          </div>
        )}
      </div>
      
      {dismissible && (
        <button
          style={dismissButtonStyle}
          onClick={handleDismiss}
          onMouseEnter={handleDismissMouseEnter}
          onMouseLeave={handleDismissMouseLeave}
          aria-label="Закрыть уведомление"
        >
          <X size={16} />
        </button>
      )}
    </div>
  );
};

export default MacOSAlert;
