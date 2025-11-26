import React, { useState, useEffect } from 'react';

const SegmentedControl = React.forwardRef(({ 
  options = [],
  value: valueProp,
  defaultValue,
  onChange,
  disabled = false,
  size = 'default',
  variant = 'default',
  className = '',
  style = {},
  ...props
}, ref) => {
  const [value, setValue] = useState(valueProp ?? defaultValue ?? (options[0]?.value ?? options[0]));

  useEffect(() => {
    if (valueProp !== undefined) setValue(valueProp);
  }, [valueProp]);

  const sizes = {
    small: { height: 24, fontSize: 11, padding: '4px 8px' },
    default: { height: 28, fontSize: 12, padding: '6px 12px' },
    large: { height: 32, fontSize: 13, padding: '8px 16px' }
  };

  const s = sizes[size] || sizes.default;

  const handleSelect = (optionValue) => {
    if (disabled) return;
    if (valueProp === undefined) setValue(optionValue);
    onChange && onChange(optionValue);
  };

  const containerStyles = {
    display: 'inline-flex',
    alignItems: 'center',
    background: 'var(--mac-bg-tertiary)',
    borderRadius: '8px',
    padding: '2px',
    border: '1px solid var(--mac-border)',
    boxShadow: 'var(--mac-shadow-1)',
    ...style
  };

  const segmentStyles = {
    height: s.height,
    fontSize: `${s.fontSize}px`,
    padding: s.padding,
    borderRadius: '6px',
    border: 'none',
    background: 'transparent',
    color: 'var(--mac-text-secondary)',
    cursor: disabled ? 'not-allowed' : 'pointer',
    transition: 'all 160ms cubic-bezier(0.2,0.8,0.2,1)',
    fontWeight: '500',
    whiteSpace: 'nowrap',
    position: 'relative',
    outline: 'none'
  };

  const activeSegmentStyles = {
    background: 'var(--mac-bg-primary)',
    color: 'var(--mac-text-primary)',
    boxShadow: 'var(--mac-shadow-2)',
    fontWeight: '600'
  };

  const disabledStyles = {
    opacity: 0.5,
    cursor: 'not-allowed'
  };

  return (
    <div 
      ref={ref}
      className={`mac-segmented-control ${className}`}
      style={containerStyles}
      role="tablist"
      aria-orientation="horizontal"
      {...props}
    >
      {options.map((option, index) => {
        const optionValue = option?.value ?? option;
        const optionLabel = option?.label ?? String(option);
        const isActive = optionValue === value;
        const isFirst = index === 0;
        const isLast = index === options.length - 1;

        return (
          <button
            key={optionValue}
            type="button"
            role="tab"
            aria-selected={isActive}
            aria-controls={`panel-${optionValue}`}
            className="mac-segment"
            style={{
              ...segmentStyles,
              ...(isActive && activeSegmentStyles),
              ...(disabled && disabledStyles),
              marginLeft: isFirst ? 0 : '1px',
              marginRight: isLast ? 0 : '1px'
            }}
            onClick={() => handleSelect(optionValue)}
            disabled={disabled}
            tabIndex={isActive ? 0 : -1}
          >
            {optionLabel}
            {isActive && (
              <div 
                className="mac-segment-indicator"
                style={{
                  position: 'absolute',
                  top: '50%',
                  left: '50%',
                  transform: 'translate(-50%, -50%)',
                  width: 'calc(100% - 4px)',
                  height: 'calc(100% - 4px)',
                  borderRadius: '4px',
                  background: 'var(--mac-accent-blue-500)',
                  opacity: 0.1,
                  pointerEvents: 'none'
                }}
              />
            )}
          </button>
        );
      })}
      <style>{`
        .mac-segment:hover:not(:disabled) {
          background: var(--mac-bg-elev-1);
          color: var(--mac-text-primary);
        }
        .mac-segment:focus-visible {
          outline: 2px solid color-mix(in srgb, var(--mac-accent-blue-500), transparent 60%);
          outline-offset: 2px;
        }
        .mac-segment:active:not(:disabled) {
          transform: scale(0.98);
        }
        @media (prefers-reduced-motion: reduce) {
          .mac-segment {
            transition: none;
          }
        }
        @media (prefers-color-scheme: dark) {
          .mac-segmented-control {
            background: var(--mac-bg-elev-1);
            border-color: var(--mac-border);
          }
        }
      `}</style>
    </div>
  );
});

export default SegmentedControl;
