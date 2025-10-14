import React, { useState } from 'react';

const Select = React.forwardRef(({ label, hint, error = false, disabled = false, size = 'default', className = '', style = {}, children, ...props }, ref) => {
  const [isFocused, setIsFocused] = useState(false);

  const sizeStyles = {
    small: { fontSize: '11px', minHeight: '28px', padding: '6px 28px 6px 10px' },
    default: { fontSize: '13px', minHeight: '32px', padding: '8px 32px 8px 12px' },
    large: { fontSize: '15px', minHeight: '40px', padding: '10px 36px 10px 14px' }
  };

  const base = {
    WebkitAppearance: 'none',
    MozAppearance: 'none',
    appearance: 'none',
    borderRadius: '6px',
    border: `1px solid ${error ? '#ff3b30' : isFocused ? 'var(--mac-focus-color)' : 'var(--mac-border)'}`,
    backgroundColor: 'var(--mac-bg-primary)',
    color: 'var(--mac-text-primary)',
    outline: 'none',
    transition: 'all 0.2s cubic-bezier(0.2, 0.8, 0.2, 1)',
    boxShadow: isFocused && !error ? 'var(--mac-focus-ring)' : 'none',
    position: 'relative',
    width: '100%'
  };

  const wrapper = { position: 'relative', display: 'inline-block', width: '100%' };

  const arrow = {
    position: 'absolute',
    right: '10px',
    top: '50%',
    transform: 'translateY(-50%)',
    pointerEvents: 'none',
    color: 'var(--mac-text-secondary)'
  };

  return (
    <div className={`mac-select-wrapper ${className}`} style={{ ...wrapper }}>
      {label && (
        <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: error ? '#ff3b30' : 'var(--mac-text-secondary)', marginBottom: '4px' }}>{label}</label>
      )}
      <select
        ref={ref}
        disabled={disabled}
        className="mac-select"
        style={{ ...base, ...sizeStyles[size], ...style }}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        {...props}
      >
        {children}
      </select>
      <span className="mac-select-arrow" style={arrow} aria-hidden>
        ▾
      </span>
      {hint && (
        <div style={{ fontSize: '11px', color: 'var(--mac-text-tertiary)', marginTop: '4px' }}>{hint}</div>
      )}

      <style jsx>{`
        @media (prefers-color-scheme: dark) {
          .mac-select {
            background-color: rgba(255, 255, 255, 0.05) !important;
            border-color: var(--mac-border) !important;
            color: #f5f5f7 !important;
          }
        }

        @media (prefers-contrast: high) {
          .mac-select { border-width: 2px !important; }
        }

        @media (prefers-reduced-motion: reduce) {
          .mac-select { transition: none !important; }
        }
      `}</style>
    </div>
  );
});

Select.displayName = 'macOS Select';

export default Select;


