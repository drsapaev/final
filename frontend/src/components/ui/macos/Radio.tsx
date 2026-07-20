import React, { useState, useEffect, type ReactNode, type CSSProperties, type ChangeEvent } from 'react';
import PropTypes from 'prop-types';

type RadioSize = 'small' | 'default' | 'large';

interface RadioProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'children' | 'style' | 'onChange' | 'size' | 'checked' | 'defaultChecked'> {
  checked?: boolean;
  defaultChecked?: boolean;
  onChange?: <T>(value: T, e: ChangeEvent<HTMLInputElement>) => void;
  name?: string;
  value?: string | number | readonly string[];
  disabled?: boolean;
  label?: ReactNode;
  description?: ReactNode;
  size?: RadioSize;
  className?: string;
  style?: CSSProperties;
  id?: string;
}

interface RadioStyle extends CSSProperties {
  transition?: string;
}

const Radio = React.forwardRef<HTMLInputElement, RadioProps>(({
  checked: checkedProp,
  defaultChecked = false,
  onChange,
  name,
  value,
  disabled = false,
  label,
  description,
  size = 'default',
  className = '',
  style = {},
  id,
  ...props
}, ref) => {
  const [isChecked, setIsChecked] = useState<boolean>(checkedProp ?? defaultChecked);

  useEffect(() => {
    if (typeof checkedProp === 'boolean') setIsChecked(checkedProp);
  }, [checkedProp]);

  const sizes: Record<RadioSize, number> = { small: 14, default: 16, large: 18 };
  const dimension = sizes[size] || sizes.default;
  const controlId = id || `rad_${Math.random().toString(36).slice(2)}`;

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (disabled) return;
    if (typeof checkedProp !== 'boolean') setIsChecked(true);
    onChange && onChange(value, e);
  };

  const wrapper: CSSProperties = {
    display: 'grid',
    gridTemplateColumns: `${dimension}px 1fr`,
    alignItems: 'center',
    gap: '8px',
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.6 : 1,
    ...style
  };

  const outer: RadioStyle = {
    width: dimension,
    height: dimension,
    borderRadius: '9999px',
    border: '1px solid var(--mac-border)',
    background: 'var(--mac-bg-elev-1)',
    position: 'relative',
    boxShadow: 'var(--mac-shadow-1)',
    transition: 'all 160ms cubic-bezier(0.2,0.8,0.2,1)'
  };

  const outerChecked: CSSProperties = isChecked ? {
    borderColor: 'var(--mac-accent-blue-500)',
    boxShadow: '0 0 0 2px color-mix(in srgb, var(--mac-accent-blue-500), transparent 70%)'
  } : {};

  const dot: RadioStyle = {
    position: 'absolute',
    left: '50%',
    top: '50%',
    width: Math.round(dimension * 0.44),
    height: Math.round(dimension * 0.44),
    transform: 'translate(-50%, -50%)',
    borderRadius: '9999px',
    background: 'var(--mac-accent-blue-500)',
    opacity: isChecked ? 1 : 0,
    transition: 'opacity var(--mac-duration-fast) var(--mac-ease)'
  };

  const title: CSSProperties = { fontSize: '13px', color: 'var(--mac-text-primary)', lineHeight: 1.3 };
  const desc: CSSProperties = { fontSize: '11px', color: 'var(--mac-text-secondary)', marginTop: '2px' };

  return (
    <label className={`mac-radio ${className}`} style={wrapper} htmlFor={controlId} aria-disabled={disabled}>
      <input
        ref={ref}
        id={controlId}
        type="radio"
        name={name}
        value={value}
        checked={!!isChecked}
        onChange={handleChange}
        disabled={disabled}
        className="mac-radio-input"
        style={{ position: 'absolute', opacity: 0, pointerEvents: 'none' }}
        {...props}
      />
      <span className="mac-radio-outer" aria-hidden style={{ ...outer, ...outerChecked }} />
      <span className="mac-radio-label" style={{ display: 'flex', flexDirection: 'column' }}>
        {label && <span style={title}>{label}</span>}
        {description && <span style={desc}>{description}</span>}
      </span>
      <span className="mac-radio-dot" aria-hidden style={dot} />
      <style>{`
        .mac-radio:hover .mac-radio-outer { box-shadow: var(--mac-shadow-2); }
        .mac-radio-input:focus-visible + .mac-radio-outer { outline: 2px solid color-mix(in srgb, var(--mac-accent-blue-500), transparent 60%); outline-offset: 2px; }
        @media (prefers-reduced-motion: reduce) {
          .mac-radio-outer { transition: none; }
        }
      `}</style>
    </label>
  );
});

Radio.displayName = 'Radio';

Radio.propTypes = {
  checked: PropTypes.bool,
  defaultChecked: PropTypes.bool,
  onChange: PropTypes.func,
  name: PropTypes.string,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  disabled: PropTypes.bool,
  label: PropTypes.node,
  description: PropTypes.node,
  size: PropTypes.oneOf(['small', 'default', 'large']),
  className: PropTypes.string,
  style: PropTypes.object,
  id: PropTypes.string
};

export default Radio;
