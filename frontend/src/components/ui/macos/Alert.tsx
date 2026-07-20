import React from 'react';
import { AlertCircle, CheckCircle, Info, AlertTriangle, X } from 'lucide-react';
import PropTypes from 'prop-types';
import { useTranslation } from '../../../i18n/useTranslation';

// SW-01 fix: merged MacOSAlert API into Alert.
// Supports both old Alert API (children + severity) and MacOSAlert API
// (type + title + description + action + dismissible).

const variantStyle = (severity) => {
  switch (severity) {
    case 'success':
      return { borderColor: 'rgba(52,199,89,0.35)', background: 'rgba(52,199,89,0.08)', color: 'var(--mac-text-primary)' };
    case 'warning':
      return { borderColor: 'rgba(255,149,0,0.35)', background: 'rgba(255,149,0,0.08)', color: 'var(--mac-text-primary)' };
    case 'error':
      return { borderColor: 'rgba(255,59,48,0.35)', background: 'rgba(255,59,48,0.08)', color: 'var(--mac-text-primary)' };
    case 'info':
    default:
      return { borderColor: 'rgba(0,122,255,0.35)', background: 'rgba(0,122,255,0.08)', color: 'var(--mac-text-primary)' };
  }
};

const typeIcons = {
  info: Info,
  success: CheckCircle,
  warning: AlertTriangle,
  error: AlertCircle,
};

interface AlertProps {
  children?: React.ReactNode;
  severity?: string;
  type?: string;
  title?: React.ReactNode;
  description?: React.ReactNode;
  action?: React.ReactNode;
  dismissible?: boolean;
  onDismiss?: () => void;
  onClose?: () => void;
  style?: React.CSSProperties;
  className?: string;
  icon?: React.ReactNode;
  role?: string;
  variant?: string;
  sx?: Record<string, unknown>;
  message?: React.ReactNode;
}

const Alert = ({
  children,
  severity = 'info',
  // MacOSAlert-compatible props
  type,
  title,
  description,
  action,
  dismissible = false,
  onDismiss,
  style = {},
  ...props
}: AlertProps) => {
  // If type is provided (MacOSAlert API), use it as severity
  const effectiveSeverity = type || severity;
  const Icon = typeIcons[effectiveSeverity] || Info;

  // MacOSAlert API: title/description/action
  if (type !== undefined || title !== undefined) {
    return (
      <div role="alert" style={{
        padding: '16px 20px',
        fontSize: 'var(--mac-font-size-base, 14px)',
        display: 'flex',
        alignItems: 'flex-start',
        gap: '12px',
        borderRadius: '12px',
        ...variantStyle(effectiveSeverity),
        ...style
      }} {...props}>
        <Icon size={20} style={{ flexShrink: 0, marginTop: '1px' }} />
        <div style={{ flex: 1, minWidth: 0 }}>
          {title && (
            <div style={{ fontWeight: 600, marginBottom: description ? '4px' : 0, fontSize: 'var(--mac-font-size-base, 14px)' }}>
              {title}
            </div>
          )}
          {description && (
            <div style={{ fontSize: '13px', opacity: 0.85 }}>
              {description}
            </div>
          )}
          {action && (
            <div style={{ marginTop: '8px' }}>
              {action}
            </div>
          )}
          {children}
        </div>
        {dismissible && (
          <button
            onClick={onDismiss}
            aria-label="Закрыть"
            style={{
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
              padding: '4px',
              flexShrink: 0,
              color: 'inherit',
              opacity: 0.6
            }}
          >
            <X size={16} />
          </button>
        )}
      </div>
    );
  }

  // Simple Alert API (children + severity)
  return (
    <div role="alert" style={{
      border: '1px solid var(--mac-border, rgba(0,0,0,0.1))',
      borderRadius: 8,
      padding: '12px 14px',
      fontSize: '13px',
      ...variantStyle(effectiveSeverity),
      ...style
    }} {...props}>
      {children}
    </div>
  );
};


Alert.propTypes = {
  ...(Alert.propTypes || {}),
  children: PropTypes.any,
  severity: PropTypes.any,
  type: PropTypes.string,
  title: PropTypes.node,
  description: PropTypes.node,
  action: PropTypes.node,
  dismissible: PropTypes.bool,
  onDismiss: PropTypes.func,
  style: PropTypes.object,
};

export default Alert;
