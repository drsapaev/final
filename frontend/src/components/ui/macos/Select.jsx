import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';

const Select = React.forwardRef(({ 
  options = [],
  value: valueProp,
  defaultValue,
  onChange,
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
  const [isOpen, setIsOpen] = useState(false);
  const [value, setValue] = useState(valueProp ?? defaultValue ?? null);
  const triggerRef = useRef(null);
  const listRef = useRef(null);
  const [dropdownRect, setDropdownRect] = useState(null);
  const [dropdownPlacement, setDropdownPlacement] = useState('bottom');

  useEffect(() => { if (valueProp !== undefined) setValue(valueProp); }, [valueProp]);

  useEffect(() => {
    const onDoc = (e) => {
      if (!triggerRef.current || !listRef.current) return;
      if (!triggerRef.current.contains(e.target) && !listRef.current.contains(e.target)) setIsOpen(false);
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
      const totalItems = Math.max(1, options?.length || 0);
      const listHeight = totalItems * itemHeight + 8; // без скролла, с внутренним отступом

      // Default bottom placement
      let top = r.bottom + 6;
      let placement = 'bottom';
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

  const sizes = {
    small: { h: 28, fs: 12, pad: '6px 8px' },
    default: { h: 32, fs: 13, pad: '8px 10px' },
    large: { h: 36, fs: 14, pad: '10px 12px' }
  };
  const s = sizes[size] || sizes.default;
  const controlId = id || `sel_${Math.random().toString(36).slice(2)}`;

  const selected = options.find(o => (o?.value ?? o) === value);

  const setAndClose = (val) => {
    if (disabled) return;
    if (valueProp === undefined) setValue(val);
    onChange && onChange(val);
    setIsOpen(false);
  };

  const wrapper = { display: 'flex', flexDirection: 'column', gap: '4px', ...style };
  const labelStyles = { fontSize: '12px', color: 'var(--mac-text-secondary)' };

  const trigger = {
    height: s.h,
    fontSize: `${s.fs}px`,
    padding: s.pad,
    borderRadius: '8px',
    border: '1px solid var(--mac-border)',
    background: disabled ? 'var(--mac-bg-tertiary)' : 'var(--mac-bg-elev-1)',
    color: 'var(--mac-text-primary)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: '8px',
    boxShadow: 'var(--mac-shadow-1)',
    cursor: disabled ? 'not-allowed' : 'pointer',
    transition: 'all 160ms cubic-bezier(0.2,0.8,0.2,1)'
  };

  const list = dropdownRect ? {
    position: 'fixed',
    left: `${dropdownRect.left}px`,
    top: `${dropdownRect.top}px`,
    minWidth: `${dropdownRect.width}px`,
    maxHeight: `${dropdownRect.height}px`,
    zIndex: 2147483000,
    borderRadius: '10px',
    border: '1px solid var(--mac-border)',
    background: 'var(--mac-bg-primary)',
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
    border: '1px solid var(--mac-border)',
    background: 'var(--mac-bg-primary)',
    boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
    overflow: 'visible',
    padding: '4px 0',
    boxSizing: 'border-box'
  };

  const item = (isActive) => ({
    padding: '8px 12px',
    fontSize: '13px',
    color: isActive ? '#ffffff' : 'var(--mac-text-primary)',
    background: isActive ? 'var(--mac-accent-blue-600)' : 'transparent',
    cursor: 'pointer',
    display: 'block'
  });

  const errorText = { fontSize: '11px', color: 'var(--mac-danger-600)' };

  return (
    <div className={`mac-select ${className}`} style={wrapper}>
      {label && <label htmlFor={controlId} style={labelStyles}>{label}</label>}
      <div style={{ position: 'relative' }}>
        <button
          ref={(node) => { triggerRef.current = node; if (typeof ref === 'function') ref(node); else if (ref) ref.current = node; }}
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
          <span>{selected ? (selected.label ?? selected.value ?? selected) : <span style={{ color: 'var(--mac-text-secondary)' }}>{placeholder}</span>}</span>
          <svg width="16" height="16" viewBox="0 0 20 20" aria-hidden>
            <path d="M6 8l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
        {isOpen && createPortal(
          <div ref={listRef} role="listbox" className="mac-select-list" style={list} data-placement={dropdownPlacement}>
            {options.map((opt) => {
              const val = opt?.value ?? opt;
              const label = opt?.label ?? String(val);
              const active = val === value;
              return (
                <div
                  key={String(val)}
                  role="option"
                  aria-selected={active}
                  className="mac-select-item"
                  style={item(active)}
                  onClick={() => setAndClose(val)}
                  onKeyDown={(e) => e.key === 'Enter' && setAndClose(val)}
                  tabIndex={0}
                >
                  {label}
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

export default Select;



