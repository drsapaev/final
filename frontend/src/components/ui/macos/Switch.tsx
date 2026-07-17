import React, { useState, useEffect, type ReactNode, type CSSProperties, type ChangeEvent } from 'react';
import PropTypes from 'prop-types';

type SwitchSize = 'small' | 'default' | 'large';

interface SwitchProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'children' | 'style' | 'onChange' | 'size' | 'checked' | 'defaultChecked'> {
  checked?: boolean;
  defaultChecked?: boolean;
  onChange?: (checked: boolean, e: ChangeEvent<HTMLInputElement>) => void;
  disabled?: boolean;
  size?: SwitchSize;
  label?: ReactNode;
  className?: string;
  style?: CSSProperties;
  id?: string;
}

interface SwitchDimensions {
  w: number;
  h: number;
  knob: number;
}

interface SwitchStyle extends CSSProperties {
  transition?: string;
}

const Switch = React.forwardRef<HTMLInputElement, SwitchProps>(({
  checked: checkedProp,
  defaultChecked = false,
  onChange,
  disabled = false,
  size = 'default',
  label,
  className = '',
  style = {},
  id,
  ...props
}, ref) => {
  const [isChecked, setIsChecked] = useState<boolean>(checkedProp ?? defaultChecked);

  useEffect(() => {
    if (typeof checkedProp === 'boolean') setIsChecked(checkedProp);
  }, [checkedProp]);

  const sizes: Record<SwitchSize, SwitchDimensions> = {
    small: { w: 34, h: 20, knob: 16 },
    default: { w: 44, h: 24, knob: 20 },
    large: { w: 54, h: 30, knob: 26 }
  };
  const s = sizes[size] || sizes.default;
  const controlId = id || `swt_${Math.random().toString(36).slice(2)}`;

  const handleToggle = (e: ChangeEvent<HTMLInputElement>) => {
    if (disabled) return;
    const next = !isChecked;
    if (typeof checkedProp !== 'boolean') setIsChecked(next);
    onChange && onChange(next, e);
  };

  const wrapper: CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '10px',
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.6 : 1,
    ...style
  };

  const track: SwitchStyle = {
    width: s.w,
    height: s.h,
    borderRadius: s.h,
    background: isChecked ? 'var(--mac-accent-blue-500)' : 'var(--mac-bg-tertiary)',
    border: '1px solid var(--mac-border)',
    boxShadow: isChecked ? '0 0 0 2px color-mix(in srgb, var(--mac-accent-blue-500), transparent 70%)' : 'var(--mac-shadow-1)',
    position: 'relative',
    transition: 'all 200ms cubic-bezier(0.2,0.8,0.2,1)'
  };

  const knob: SwitchStyle = {
    position: 'absolute',
    top: 1,
    left: isChecked ? s.w - s.knob - 1 : 1,
    width: s.knob,
    height: s.knob,
    borderRadius: s.knob,
    background: 'var(--mac-bg-primary)',
    boxShadow: '0 1px 2px rgba(0,0,0,0.2)',
    transition: 'left 200ms cubic-bezier(0.2,0.8,0.2,1)'
  };

  const labelStyles: CSSProperties = { fontSize: '13px', color: 'var(--mac-text-primary)' };
  const ariaLabelProp = props['aria-label'] as string | undefined;
  const accessibleLabel = ariaLabelProp || (typeof label === 'string' ? label : 'Toggle setting');

  return (
    <label className={`mac-switch ${className}`} style={wrapper} htmlFor={controlId} aria-disabled={disabled}>
      <input
        ref={ref}
        id={controlId}
        type="checkbox"
        role="switch"
        checked={!!isChecked}
        onChange={handleToggle}
        disabled={disabled}
        className="mac-switch-input"
        style={{ position: 'absolute', opacity: 0, pointerEvents: 'none' }}
        aria-label={accessibleLabel}
        {...props}
      />
      <span className="mac-switch-track" aria-hidden style={track}>
        <span className="mac-switch-knob" aria-hidden style={knob} />
      </span>
      {label && <span className="mac-switch-label" style={labelStyles}>{label}</span>}
      <style>{`
        .mac-switch:hover .mac-switch-track { filter: brightness(1.03); }
        .mac-switch-input:focus-visible + .mac-switch-track { outline: 2px solid color-mix(in srgb, var(--mac-accent-blue-500), transparent 60%); outline-offset: 2px; }
        @media (prefers-reduced-motion: reduce) {
          .mac-switch-track, .mac-switch-knob { transition: none; }
        }
      `}</style>
    </label>
  );
});


Switch.propTypes = {
  ...(Switch.propTypes || {}),
  checked: PropTypes.any,
  className: PropTypes.any,
  defaultChecked: PropTypes.any,
  disabled: PropTypes.any,
  id: PropTypes.any,
  label: PropTypes.any,
  onChange: PropTypes.any,
  size: PropTypes.any,
  style: PropTypes.any,
};

Switch.displayName = 'Switch';

export default Switch;
