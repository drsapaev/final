import React, { useState, useEffect } from 'react';

const Checkbox = React.forwardRef(({ 
  checked: checkedProp,
  defaultChecked = false,
  onChange,
  disabled = false,
  label,
  description,
  size = 'default',
  variant = 'default',
  className = '',
  style = {},
  id,
  ...props
}, ref) => {
  const [isChecked, setIsChecked] = useState(checkedProp ?? defaultChecked);

  useEffect(() => {
    if (typeof checkedProp === 'boolean') setIsChecked(checkedProp);
  }, [checkedProp]);

  const sizes = {
    small: 14,
    default: 16,
    large: 18
  };

  const dimension = sizes[size] || sizes.default;
  const controlId = id || `chk_${Math.random().toString(36).slice(2)}`;

  const handleToggle = (e) => {
    if (disabled) return;
    const next = !isChecked;
    if (typeof checkedProp !== 'boolean') setIsChecked(next);
    onChange && onChange(next, e);
  };

  const wrapperStyles = {
    display: 'grid',
    gridTemplateColumns: `${dimension}px 1fr`,
    alignItems: 'center',
    gap: '8px',
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.6 : 1,
    ...style
  };

  const boxStyles = {
    width: dimension,
    height: dimension,
    borderRadius: '4px',
    border: `1px solid var(--mac-border)`,
    background: 'var(--mac-bg-elev-1)',
    position: 'relative',
    boxShadow: 'var(--mac-shadow-1)',
    transition: 'all 160ms cubic-bezier(0.2,0.8,0.2,1)'
  };

  const boxStylesChecked = isChecked ? {
    borderColor: 'var(--mac-accent-blue-500)',
    background: 'var(--mac-accent-blue-500)',
    boxShadow: '0 0 0 2px color-mix(in srgb, var(--mac-accent-blue-500), transparent 70%)'
  } : {};

  const checkStyles = {
    position: 'absolute',
    left: '50%',
    top: '50%',
    transform: 'translate(-50%, -50%) scale(1)',
    color: 'var(--mac-bg-primary)',
    opacity: isChecked ? 1 : 0,
    transition: 'opacity var(--mac-duration-fast) var(--mac-ease)',
    pointerEvents: 'none'
  };

  const labelStyles = {
    display: 'flex',
    flexDirection: 'column'
  };

  const titleStyles = {
    fontSize: '13px',
    color: 'var(--mac-text-primary)',
    lineHeight: 1.3
  };

  const descStyles = {
    fontSize: '11px',
    color: 'var(--mac-text-secondary)',
    marginTop: '2px'
  };

  return (
    <label className={`mac-checkbox ${className}`} style={wrapperStyles} htmlFor={controlId} aria-disabled={disabled}>
      <input
        ref={ref}
        id={controlId}
        type="checkbox"
        checked={!!isChecked}
        onChange={handleToggle}
        disabled={disabled}
        className="mac-checkbox-input"
        style={{ position: 'absolute', opacity: 0, pointerEvents: 'none' }}
        {...props}
      />
      <span className="mac-checkbox-box" aria-hidden style={{ ...boxStyles, ...boxStylesChecked }} />
      <span className="mac-checkbox-label" style={labelStyles}>
        {label && <span style={titleStyles}>{label}</span>}
        {description && <span style={descStyles}>{description}</span>}
      </span>
      <svg width={dimension} height={dimension} viewBox="0 0 20 20" style={checkStyles} aria-hidden>
        <path d="M5 10.5l3 3 7-7" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <style>{`
        .mac-checkbox:hover .mac-checkbox-box { box-shadow: var(--mac-shadow-2); }
        .mac-checkbox-input:focus-visible + .mac-checkbox-box { outline: 2px solid color-mix(in srgb, var(--mac-accent-blue-500), transparent 60%); outline-offset: 2px; }
        @media (prefers-reduced-motion: reduce) {
          .mac-checkbox-box { transition: none; }
        }
      `}</style>
    </label>
  );
});

export default Checkbox;



