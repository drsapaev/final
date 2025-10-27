import React from 'react';

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

const Alert = ({ children, severity = 'info', style = {}, ...props }) => {
  return (
    <div style={{
      border: '1px solid var(--mac-border)',
      borderRadius: 8,
      padding: '12px 14px',
      fontSize: '13px',
      ...variantStyle(severity),
      ...style
    }} {...props}>
      {children}
    </div>
  );
};

export default Alert;


