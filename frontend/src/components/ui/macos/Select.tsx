import React, { useState, useRef, useEffect, type CSSProperties, type ReactNode, type KeyboardEvent } from 'react';
import PropTypes from 'prop-types';
import { createPortal } from 'react-dom';
import { useTranslation } from '../../../i18n/useTranslation';
import { toFormValue } from '../../../utils/formValue';

type SelectSize = 'small' | 'default' | 'large';
type SelectValue = string | number;
type SelectPlacement = 'bottom' | 'top';

interface SelectOption {
  value: SelectValue;
  label?: ReactNode;
}

interface DropdownRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

/**
 * Event-like object emitted by Select's `onChange`.
 * Compatible with legacy callers that do `e.target.value`.
 * @deprecated Use `onValueChange` instead for new code.
 */
export interface SelectChangeEvent {
  target: {
    value: string;
    name?: string;
  };
}

interface SelectProps extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'style' | 'onChange' | 'size' | 'value' | 'defaultValue' | 'label'> {
  /** Optional children — used by legacy callers that wrap <option> tags inside <select> via this component. */
  children?: ReactNode;
  options?: Array<SelectOption | SelectValue>;
  value?: SelectValue | string;
  defaultValue?: SelectValue;
  /**
   * Legacy event-like handler. Receives a synthetic event with `target.value`.
   * @deprecated Use `onValueChange` for new code — it passes the raw value directly.
   */
  onChange?: (event: SelectChangeEvent) => void;
  /**
   * Value-based handler. Receives the selected value directly (string or number).
   * Preferred over `onChange` for new code.
   */
  onValueChange?: (value: SelectValue) => void;
  placeholder?: ReactNode;
  disabled?: boolean;
  size?: SelectSize;
  label?: ReactNode;
  error?: ReactNode;
  className?: string;
  style?: CSSProperties;
  id?: string;
}

interface SelectStyle extends CSSProperties {
  transition?: string;
}

interface SelectDimensions {
  h: number;
  fs: number;
  pad: string;
}

function normalizeOption(opt: SelectOption | SelectValue): SelectOption {
  if (opt !== null && typeof opt === 'object' && 'value' in (opt as SelectOption)) {
    return opt as SelectOption;
  }
  const v = opt as SelectValue;
  return { value: v, label: String(v) };
}

const Select = React.forwardRef<HTMLButtonElement, SelectProps>(({
  options = [],
  value: valueProp,
  defaultValue,
  onChange,
  onValueChange,
  placeholder = 'Select…',
  disabled = false,
  size = 'default',
  label,
  error,
  className = '',
  style = {},
  id,
  ...props
}, ref) => {
  const { t } = useTranslation();
  void t;
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [value, setValue] = useState<SelectValue | undefined>(valueProp ?? defaultValue);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);
  const [dropdownRect, setDropdownRect] = useState<DropdownRect | null>(null);
  const [dropdownPlacement, setDropdownPlacement] = useState<SelectPlacement>('bottom');

  useEffect(() => { if (valueProp !== undefined) setValue(valueProp); }, [valueProp]);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      const target = e.target as Node | null;
      if (!triggerRef.current || !listRef.current) return;
      if (!triggerRef.current.contains(target) && !listRef.current.contains(target)) setIsOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  // Recompute dropdown position when opened or on viewport changes
  useEffect(() => {
    if (!isOpen) return;
    const updateRect = () => {
      if (!triggerRef.current) return;
      const r = triggerRef.current.getBoundingClientRect();
      const itemHeight = 32;
      const normalizedOptions = options.map(normalizeOption);
      const totalItems = Math.max(1, normalizedOptions.length);
      const listHeight = totalItems * itemHeight + 8; // без скролла, с внутренним отступом

      // Default bottom placement
      let top = r.bottom + 6;
      let placement: SelectPlacement = 'bottom';
      // Flip above if not enough space below
      if (top + listHeight + 8 > window.innerHeight) {
        const maybeTop = r.top - listHeight - 6;
        if (maybeTop >= 8) {
          top = maybeTop;
          placement = 'top';
        } else {
          // Clamp inside viewport
          top = Math.max(8, Math.min(top, window.innerHeight - listHeight - 8));
        }
      }

      const minWidth = Math.max(160, r.width);
      const left = Math.max(8, Math.min(r.left, window.innerWidth - minWidth - 8));

      setDropdownPlacement(placement);
      setDropdownRect({ left, top, width: minWidth, height: listHeight });
    };
    updateRect();
    window.addEventListener('scroll', updateRect, true);
    window.addEventListener('resize', updateRect);
    return () => {
      window.removeEventListener('scroll', updateRect, true);
      window.removeEventListener('resize', updateRect);
    };
  }, [isOpen, options]);

  const sizes: Record<SelectSize, SelectDimensions> = {
    small: { h: 28, fs: 12, pad: '6px 8px' },
    default: { h: 32, fs: 13, pad: '8px 10px' },
    large: { h: 36, fs: 14, pad: '10px 12px' }
  };
  const s = sizes[size] || sizes.default;
  const controlId = id || `sel_${Math.random().toString(36).slice(2)}`;

  const normalizedOptions = options.map(normalizeOption);
  const selected = normalizedOptions.find(o => o.value === value);

  const setAndClose = (val: SelectValue) => {
    if (disabled) return;
    if (valueProp === undefined) setValue(val);
    // Emit value-based event for new callers
    onValueChange?.(val);
    // Emit event-like object for legacy callers (deprecated)
    onChange?.({ target: { value: toFormValue(val) } });
    setIsOpen(false);
  };

  const wrapper: CSSProperties = { display: 'flex', flexDirection: 'column', gap: '4px', ...style };
  const labelStyles: CSSProperties = { fontSize: '12px', color: 'var(--mac-text-secondary)' };

  const trigger: SelectStyle = {
    height: s.h,
    fontSize: `${s.fs}px`,
    padding: s.pad,
    borderRadius: '8px',
    border: '1px solid var(--mac-card-border, var(--mac-border))',
    background: disabled ?
    'color-mix(in srgb, var(--mac-card-bg, var(--mac-bg-tertiary)), var(--mac-main-shell-bg, var(--mac-bg-secondary)) 38%)' :
    'color-mix(in srgb, var(--mac-card-bg, var(--mac-bg-primary)), var(--mac-main-shell-bg, var(--mac-bg-secondary)) 24%)',
    color: 'var(--mac-text-primary)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: '8px',
    boxShadow: 'var(--mac-shadow-sm)',
    cursor: disabled ? 'not-allowed' : 'pointer',
    transition: 'all 160ms cubic-bezier(0.2,0.8,0.2,1)'
  };

  const list: CSSProperties = dropdownRect ? {
    position: 'fixed',
    left: `${dropdownRect.left}px`,
    top: `${dropdownRect.top}px`,
    minWidth: `${dropdownRect.width}px`,
    maxHeight: `${dropdownRect.height}px`,
    zIndex: 2147483000,
    borderRadius: '10px',
    border: '1px solid var(--mac-card-border, var(--mac-border))',
    background: 'var(--mac-card-bg, var(--mac-bg-primary))',
    boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
    overflow: 'visible',
    padding: '4px 0',
    boxSizing: 'border-box'
  } : {
    position: 'fixed',
    left: '0px',
    top: '0px',
    minWidth: '160px',
    zIndex: 2147483000,
    borderRadius: '10px',
    border: '1px solid var(--mac-card-border, var(--mac-border))',
    background: 'var(--mac-card-bg, var(--mac-bg-primary))',
    boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
    overflow: 'visible',
    padding: '4px 0',
    boxSizing: 'border-box'
  };

  const item = (isActive: boolean): CSSProperties => ({
    padding: '8px 12px',
    fontSize: '13px',
    color: isActive ? 'var(--mac-bg-primary)' : 'var(--mac-text-primary)',
    background: isActive ? 'var(--mac-accent-blue-600)' : 'transparent',
    cursor: 'pointer',
    display: 'block'
  });

  const errorText: CSSProperties = { fontSize: '11px', color: 'var(--mac-danger-600)' };

  const setTriggerRef = (node: HTMLButtonElement | null) => {
    triggerRef.current = node;
    if (typeof ref === 'function') ref(node);
    else if (ref) (ref as React.MutableRefObject<HTMLButtonElement | null>).current = node;
  };

  return (
    <div className={`mac-select ${className}`} style={wrapper}>
      {label && <label htmlFor={controlId} style={labelStyles}>{label}</label>}
      <div style={{ position: 'relative' }}>
        <button
          ref={setTriggerRef}
          id={controlId}
          type="button"
          className="mac-select-trigger"
          onClick={() => !disabled && setIsOpen(!isOpen)}
          style={trigger}
          aria-haspopup="listbox"
          aria-expanded={isOpen}
          disabled={disabled}
          {...props}
        >
          <span>{selected ? (selected.label ?? String(selected.value)) : <span style={{ color: 'var(--mac-text-secondary)' }}>{placeholder}</span>}</span>
          <svg width="16" height="16" viewBox="0 0 20 20" aria-hidden>
            <path d="M6 8l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
        {isOpen && createPortal(
          <div ref={listRef} role="listbox" className="mac-select-list" style={list} data-placement={dropdownPlacement}>
            {normalizedOptions.map((opt) => {
              const val = opt.value;
              const lbl = opt.label ?? String(val);
              const active = val === value;
              return (
                <div
                  key={String(val)}
                  role="option"
                  aria-selected={active}
                  className="mac-select-item"
                  style={item(active)}
                  onClick={() => setAndClose(val)}
                  onKeyDown={(e: KeyboardEvent<HTMLDivElement>) => { if (e.key === 'Enter') setAndClose(val); }}
                  tabIndex={0}
                >
                  {lbl}
                </div>
              );
            })}
          </div>, document.body)
        }
      </div>
      {error && <div className="mac-select-error" role="alert" style={errorText}>{error}</div>}
      <style>{`
        .mac-select-trigger:hover { box-shadow: var(--mac-shadow-2); }
        .mac-select-trigger:focus-visible { outline: 2px solid color-mix(in srgb, var(--mac-accent-blue-500), transparent 60%); outline-offset: 2px; }
        .mac-select-item:hover { background: color-mix(in srgb, var(--mac-accent-blue-500), transparent 92%); color: var(--mac-accent-blue-700); }
        @media (prefers-reduced-motion: reduce) {
          .mac-select-trigger { transition: none; }
        }
      `}</style>
    </div>
  );
});

Select.displayName = 'Select';

Select.propTypes = {
  options: PropTypes.arrayOf(
    PropTypes.oneOfType([
      PropTypes.string,
      PropTypes.number,
      PropTypes.shape({
        value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
        label: PropTypes.node
      })
    ])
  ),
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  defaultValue: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  onChange: PropTypes.func,
  placeholder: PropTypes.node,
  disabled: PropTypes.bool,
  size: PropTypes.oneOf(['small', 'default', 'large']),
  label: PropTypes.node,
  error: PropTypes.oneOfType([PropTypes.bool, PropTypes.node]),
  className: PropTypes.string,
  style: PropTypes.object,
  id: PropTypes.string
};

export default Select;
